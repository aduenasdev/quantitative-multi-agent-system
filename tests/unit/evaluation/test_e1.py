from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qmas import cli
from qmas.contracts.verdict import Verdict
from qmas.evaluation import (
    CALIBRATION_SEEDS,
    JUDGEMENT_SEEDS,
    TEMPLATES,
    E1Report,
    evaluate_case,
    render_markdown,
    run_e1,
    write_report,
)
from qmas.evaluation.cases import DEFECTS, SIGNALS, build_context
from qmas.evaluation.e1 import CaseOutcome, _criteria
from qmas.red_team import BatteryThresholds

QUICK = BatteryThresholds(placebo_runs=5)
TEMPLATE = {template.case_id: template for template in TEMPLATES}


def outcome(case_id: str, verdict: Verdict, claimed: float = 1.0) -> CaseOutcome:
    template = TEMPLATE[case_id]
    return CaseOutcome(
        case_id=case_id,
        kind=template.kind,
        seed=1,
        claimed_sharpe=claimed,
        verdict=verdict,
        failed_attacks=("A1",) if verdict in {Verdict.BROKEN, Verdict.WOUNDED} else (),
        expected_attacks=template.expected_attacks,
        is_claim=template.kind == "signal" or claimed > 0,
        caught=verdict in {Verdict.BROKEN, Verdict.WOUNDED},
        caught_by_expected=False,
    )


def test_case_library_matches_the_evaluation_plan() -> None:
    assert [t.case_id for t in DEFECTS] == [f"P{n}" for n in range(1, 11)]
    assert [t.planted_ic for t in SIGNALS] == [0.0, 0.01, 0.02, 0.04, 0.08]
    assert all(t.expected_attacks for t in DEFECTS)
    assert not set(CALIBRATION_SEEDS) & set(JUDGEMENT_SEEDS)


def test_selection_case_reports_the_best_of_its_trials() -> None:
    template = replace(TEMPLATE["P4"], selection_trials=8)
    context = build_context(template, 1000, QUICK)
    assert context.trials.n_trials == 8
    assert context.trials.returns is not None
    assert context.trials.returns.shape[1] == 8
    assert context.claimed_sharpe == pytest.approx(
        max(context.trials.returns.mean(axis=0) / context.trials.returns.std(axis=0, ddof=1))
        * 252**0.5,
        rel=1e-6,
    )


def test_evaluate_case_on_a_defect() -> None:
    result = evaluate_case(TEMPLATE["P1"], 1000, QUICK)
    assert result.verdict is Verdict.BROKEN
    assert result.caught
    assert result.caught_by_expected
    assert result.is_claim


def test_criteria_count_only_positive_defect_claims() -> None:
    outcomes = [
        outcome("P1", Verdict.BROKEN),
        outcome("P5", Verdict.NOT_PROVABLE, claimed=-0.2),
        outcome("IC0.00", Verdict.WOUNDED),
        outcome("IC0.08", Verdict.SURVIVES),
    ]
    caught, noise, signals = _criteria(outcomes, {"IC0.08"})
    assert (caught.value, caught.passed) == (1.0, True)
    assert "1 defect case(s) without a positive claim left out" in caught.detail
    assert (noise.value, noise.passed) == (0.0, True)
    assert (signals.value, signals.passed) == (1.0, True)
    missed = _criteria([outcome("P1", Verdict.SURVIVES)], set())
    assert not missed[0].passed
    assert missed[1].value is None
    assert not missed[2].passed


def test_run_e1_on_a_subset_and_render(tmp_path: Path) -> None:
    progress: list[str] = []
    report = run_e1(
        (1000,),
        QUICK,
        workers=1,
        progress=lambda o: progress.append(o.case_id),
        templates=(TEMPLATE["P1"], TEMPLATE["IC0.08"]),
    )
    assert progress == ["P1", "IC0.08"]
    assert report.confusion["P1"]["BROKEN"] == 1
    assert report.minimum_detectable_sharpe > 0
    assert set(report.expected_signal_sharpe) == {"IC0.01", "IC0.02", "IC0.04", "IC0.08"}
    markdown = render_markdown(report)
    assert "## Confusion matrix" in markdown
    assert "| P1 | signal uses the next day's return |" in markdown
    json_path, markdown_path = write_report(report, tmp_path / "reports", "e1-test")
    assert E1Report.model_validate(json.loads(json_path.read_text(encoding="utf-8"))) == report
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_run_e1_in_parallel_matches_serial() -> None:
    templates = (TEMPLATE["P1"],)
    serial = run_e1((1000,), QUICK, workers=1, templates=templates)
    parallel = run_e1((1000,), QUICK, workers=2, templates=templates)
    assert serial.outcomes == parallel.outcomes


def test_cli_evaluate_e1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_run_e1(
        seeds: tuple[int, ...],
        thresholds: BatteryThresholds,
        workers: int | None = None,
        progress: Callable[[CaseOutcome], None] | None = None,
    ) -> E1Report:
        calls["seeds"], calls["placebo_runs"] = seeds, thresholds.placebo_runs
        return run_e1((1000,), QUICK, workers=1, progress=progress, templates=(TEMPLATE["P1"],))

    monkeypatch.setattr(cli, "run_e1", fake_run_e1)
    result = CliRunner().invoke(
        cli.app, ["evaluate", "e1", "--split", "calibration", "--quick", "--output", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert calls == {"seeds": CALIBRATION_SEEDS[:2], "placebo_runs": cli.QUICK_PLACEBO_RUNS}
    assert "P1 seed 1000: BROKEN" in result.output
    assert "[pass] defects caught" in result.output
    assert (tmp_path / "e1-calibration-quick.md").is_file()
