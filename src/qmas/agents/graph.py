"""The research desk as a LangGraph state machine.

    register -> quant -> red_team -> reporter -> human_gate -> END

* ``register`` (orchestrator) validates the thesis and writes its hash to the ledger
  (RULE-PREREG-01);
* ``quant`` re-runs the claimed backtest on the design window and records the trial
  (RULE-TRIALS-01);
* ``red_team`` runs the deterministic battery (RULE-LLM-01) and records the verdict;
* ``reporter`` writes the memo with the LLM layer, audited figure by figure (RULE-AUDIT-01);
* ``human_gate`` pauses until a person approves or rejects, and records the decision
  (RULE-HUMAN-01).

Routing is fixed: no model chooses the next step (ADR 0002). Every node checks the stage it expects
and raises ``IllegalTransitionError`` otherwise. State is checkpointed in SQLite, so a paused thesis
survives a restart and is resumed by its thread id, the thesis key.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from qmas.agents.memo import write_memo
from qmas.backtest import market_from_thesis, run_backtest, strategy_from_thesis
from qmas.config import Settings
from qmas.contracts.thesis import Thesis
from qmas.contracts.verdict import RedTeamReport
from qmas.ledger import Ledger
from qmas.llm import PromptRegistry, build_client
from qmas.red_team import FULL_BATTERY, AttackContext, BatteryThresholds, TrialSet, run_battery

Stage = Literal["received", "registered", "backtested", "judged", "reported", "decided"]
Decision = Literal["approved", "rejected"]


class IllegalTransitionError(RuntimeError):
    """Raised when a node runs out of order."""


class DeskState(TypedDict, total=False):
    """Checkpointed state of one thesis (JSON-friendly values only)."""

    thesis: dict[str, Any]
    stage: Stage
    claimed_sharpe: float
    report: dict[str, Any]
    memo: str
    memo_source: str
    decision: Decision
    reviewer_note: str


def _require(state: DeskState, expected: Stage, node: str) -> Thesis:
    stage = state.get("stage")
    if stage != expected:
        raise IllegalTransitionError(f"{node} needs stage {expected!r}, got {stage!r}")
    return Thesis.model_validate(state["thesis"])


@dataclass
class Desk:
    """Dependencies shared by the nodes."""

    settings: Settings
    thresholds: BatteryThresholds

    @property
    def ledger(self) -> Ledger:
        """Return the ledger in the data directory."""
        return Ledger(self.settings.data_dir / "ledger.jsonl")

    def register(self, state: DeskState) -> DeskState:
        """Orchestrator: pre-register the thesis (RULE-PREREG-01)."""
        thesis = _require(state, "received", "register")
        self.ledger.register_thesis(thesis)
        return {"stage": "registered"}

    def quant(self, state: DeskState) -> DeskState:
        """Quant: reproduce the claim on the design window and record the trial."""
        thesis = _require(state, "registered", "quant")
        self.ledger.require_registered(thesis)
        result = run_backtest(market_from_thesis(thesis), strategy_from_thesis(thesis))
        sharpe = result.sharpe()
        self.ledger.append(
            "trial",
            {"family": thesis.family, "key": thesis.key, "window": "design", "sharpe": sharpe},
        )
        return {"stage": "backtested", "claimed_sharpe": sharpe}

    def red_team(self, state: DeskState) -> DeskState:
        """Red team: run the full deterministic battery and record the verdict."""
        thesis = _require(state, "backtested", "red_team")
        trials = TrialSet(n_trials=max(1, self.ledger.count_trials(thesis.family)))
        context = AttackContext(
            market_from_thesis(thesis),
            strategy_from_thesis(thesis),
            trials,
            self.thresholds,
            self.settings.seed,
        )
        report = run_battery(context, FULL_BATTERY)
        self.ledger.append(
            "verdict",
            {
                "family": thesis.family,
                "key": thesis.key,
                "verdict": report.verdict.value,
                "failed_attacks": list(report.failed()),
                "claimed_sharpe": report.claimed_sharpe,
            },
        )
        return {"stage": "judged", "report": report.model_dump(mode="json")}

    def reporter(self, state: DeskState) -> DeskState:
        """Write the memo: LLM when configured and audited, template otherwise (reporter)."""
        thesis = _require(state, "judged", "reporter")
        report = RedTeamReport.model_validate(state["report"])
        client = build_client(self.settings)
        try:
            memo = write_memo(thesis, report, client, PromptRegistry())
        finally:
            client.close()
        return {"stage": "reported", "memo": memo.text, "memo_source": memo.source}

    def human_gate(self, state: DeskState) -> DeskState:
        """Human gate: pause for a decision, then record it (RULE-HUMAN-01)."""
        thesis = _require(state, "reported", "human_gate")
        answer = interrupt(
            {
                "key": thesis.key,
                "verdict": state["report"]["verdict"],
                "memo": state["memo"],
                "question": "approve or reject?",
            }
        )
        decision: Decision = "approved" if answer.get("decision") == "approved" else "rejected"
        note = str(answer.get("note", ""))
        self.ledger.append(
            "decision",
            {
                "family": thesis.family,
                "key": thesis.key,
                "decision": decision,
                "verdict": state["report"]["verdict"],
                "note": note,
            },
        )
        return {"stage": "decided", "decision": decision, "reviewer_note": note}


def build_graph(desk: Desk, checkpointer: SqliteSaver | None = None) -> CompiledStateGraph[Any]:
    """Wire the nodes in their fixed order."""
    graph: StateGraph[DeskState] = StateGraph(DeskState)
    graph.add_node("register", desk.register)
    graph.add_node("quant", desk.quant)
    graph.add_node("red_team", desk.red_team)
    graph.add_node("reporter", desk.reporter)
    graph.add_node("human_gate", desk.human_gate)
    graph.add_edge(START, "register")
    graph.add_edge("register", "quant")
    graph.add_edge("quant", "red_team")
    graph.add_edge("red_team", "reporter")
    graph.add_edge("reporter", "human_gate")
    graph.add_edge("human_gate", END)
    return graph.compile(checkpointer=checkpointer)


def open_checkpointer(data_dir: Path) -> SqliteSaver:
    """Return the SQLite checkpointer of the data directory."""
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "checkpoints.sqlite3", check_same_thread=False)
    return SqliteSaver(connection)


@contextmanager
def open_desk(
    settings: Settings, thresholds: BatteryThresholds
) -> Iterator[CompiledStateGraph[Any]]:
    """Yield the desk graph with its checkpointer, and close the checkpointer afterwards."""
    checkpointer = open_checkpointer(settings.data_dir)
    try:
        yield build_graph(Desk(settings, thresholds), checkpointer)
    finally:
        checkpointer.conn.close()


def thread(key: str) -> RunnableConfig:
    """Return the LangGraph config of one thesis."""
    return {"configurable": {"thread_id": key}}


def start(graph: CompiledStateGraph[Any], thesis: Thesis) -> dict[str, Any]:
    """Run a thesis until the human gate (or the end)."""
    initial: DeskState = {"thesis": thesis.model_dump(mode="json"), "stage": "received"}
    result: dict[str, Any] = graph.invoke(initial, thread(thesis.key))
    return result


def decide(
    graph: CompiledStateGraph[Any], key: str, decision: Decision, note: str = ""
) -> dict[str, Any]:
    """Resume a paused thesis with a human decision."""
    snapshot = graph.get_state(thread(key))
    if "human_gate" not in snapshot.next:
        raise IllegalTransitionError(f"{key} is not waiting for a decision")
    command: Command[Any] = Command(resume={"decision": decision, "note": note})
    result: dict[str, Any] = graph.invoke(command, thread(key))
    return result
