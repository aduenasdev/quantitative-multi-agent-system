from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from qmas.agents import (
    Desk,
    IllegalTransitionError,
    decide,
    open_desk,
    start,
    template_memo,
    thread,
    write_memo,
)
from qmas.agents.memo import allowed_numbers
from qmas.cli import app
from qmas.config import Settings
from qmas.contracts.verdict import (
    AttackOutcome,
    AttackResult,
    RedTeamReport,
    Severity,
    Verdict,
)
from qmas.ledger import Ledger
from qmas.llm import LLMClient, LLMRequest, LLMResponse, PromptRegistry
from qmas.red_team import BatteryThresholds
from tests.factories import make_thesis, thesis_document

QUICK = BatteryThresholds(placebo_runs=10)
SMALL_MARKET = {
    "source": "synthetic",
    "seed": 7,
    "parameters": {"n_assets": 60, "planted_ic": 0.08},
}

REPORT = RedTeamReport(
    verdict=Verdict.WOUNDED,
    claimed_sharpe=1.2345,
    suspicious=False,
    attacks=(
        AttackResult(
            attack_id="A3",
            name="trading costs",
            severity=Severity.SERIOUS,
            outcome=AttackOutcome.FAILED,
            metrics={"net_sharpe": -0.21},
            message="with realistic costs the Sharpe ratio is -0.21",
        ),
        AttackResult(
            attack_id="A1",
            name="look-ahead leakage",
            severity=Severity.FATAL,
            outcome=AttackOutcome.PASSED,
            metrics={"retention": 0.93},
            message="one day of delay keeps 93% of the Sharpe ratio",
        ),
    ),
)


class ScriptedProvider:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, text: str) -> None:
        self.text = text

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=self.text, provider=self.name, model=self.model)


def desk_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def small_thesis(**overrides: Any) -> Any:
    return make_thesis(data=SMALL_MARKET, **overrides)


def test_template_memo_lists_the_decisive_attack() -> None:
    memo = template_memo(make_thesis(), REPORT)
    assert "WOUNDED" in memo
    assert "A3 trading costs" in memo
    assert "Passed: A1" in memo


def test_llm_memo_is_kept_only_if_its_numbers_check_out(tmp_path: Path) -> None:
    thesis = make_thesis()
    settings = desk_settings(tmp_path)
    honest = LLMClient(
        ScriptedProvider("WOUNDED: costs turn 1.23 into -0.21; 93% kept."),
        tmp_path / "a.db",
        settings,
    )
    accepted = write_memo(thesis, REPORT, honest, PromptRegistry())
    assert accepted.source == "scripted:scripted-1"
    inventive = LLMClient(
        ScriptedProvider("WOUNDED with a Sharpe of 2.75."), tmp_path / "b.db", settings
    )
    rejected = write_memo(thesis, REPORT, inventive, PromptRegistry())
    assert rejected.source.startswith("template")
    assert rejected.unknown_numbers == ("2.75",)
    assert rejected.text == template_memo(thesis, REPORT)
    honest.close()
    inventive.close()


def test_allowed_numbers_include_thesis_figures() -> None:
    numbers = allowed_numbers(
        make_thesis(hypothesis="Holds for 21 sessions after 3 events."), REPORT
    )
    assert {21.0, 3.0, -0.21, 0.93} <= set(numbers)


def test_full_run_pauses_and_resumes_after_a_restart(tmp_path: Path) -> None:
    settings = desk_settings(tmp_path)
    thesis = small_thesis()
    with open_desk(settings, QUICK) as first:
        paused = start(first, thesis)
    assert paused["stage"] == "reported"
    assert paused["__interrupt__"][0].value["key"] == thesis.key
    assert paused["report"]["verdict"] in {verdict.value for verdict in Verdict}

    # A new graph and checkpointer, as after closing the process.
    with open_desk(settings, QUICK) as second:
        assert second.get_state(thread(thesis.key)).next == ("human_gate",)
        done = decide(second, thesis.key, "rejected", "not convinced")
        with pytest.raises(IllegalTransitionError, match="not waiting"):
            decide(second, thesis.key, "approved")
    assert (done["stage"], done["decision"], done["reviewer_note"]) == (
        "decided",
        "rejected",
        "not convinced",
    )

    entries = list(Ledger(settings.data_dir / "ledger.jsonl").entries())
    assert [entry.kind for entry in entries] == [
        "thesis_registered",
        "trial",
        "verdict",
        "decision",
    ]
    assert entries[-1].payload["decision"] == "rejected"


def test_nodes_refuse_to_run_out_of_order(tmp_path: Path) -> None:
    desk = Desk(desk_settings(tmp_path), QUICK)
    state: Any = {"thesis": small_thesis().model_dump(mode="json"), "stage": "received"}
    with pytest.raises(IllegalTransitionError, match="quant needs stage 'registered'"):
        desk.quant(state)
    with pytest.raises(IllegalTransitionError, match="human_gate"):
        desk.human_gate(state)


def test_cli_thesis_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMAS_DATA_DIR", str(tmp_path / "data"))
    path = tmp_path / "thesis.yaml"
    path.write_text(yaml.safe_dump(thesis_document(data=SMALL_MARKET)), encoding="utf-8")
    runner = CliRunner()

    ran = runner.invoke(app, ["thesis", "run", str(path), "--quick"])
    assert ran.exit_code == 0, ran.output
    assert "awaiting a decision: qmas thesis approve test-thesis-v1" in ran.output
    assert "stage reported" in runner.invoke(app, ["thesis", "status", "test-thesis-v1"]).output

    approved = runner.invoke(app, ["thesis", "approve", "test-thesis-v1", "--note", "ok"])
    assert approved.exit_code == 0, approved.output
    assert "approved" in approved.output
    status = runner.invoke(app, ["thesis", "status", "test-thesis-v1"]).output
    assert "decision: approved ok" in status

    again = runner.invoke(app, ["thesis", "run", str(path)])
    assert again.exit_code == 1
    assert "new version" in again.output
    assert runner.invoke(app, ["thesis", "reject", "test-thesis-v1"]).exit_code == 1
    assert runner.invoke(app, ["thesis", "status", "missing-v1"]).exit_code == 1
