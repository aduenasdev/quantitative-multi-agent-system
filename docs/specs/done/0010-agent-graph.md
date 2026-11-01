# Spec 0010: Wire the agents into a graph with a human gate

- **Status**: done
- **Depends on**: 0003, 0006, 0007, 0009
- **Blocks**: 0011
- **Size**: L
- **Last updated**: 2026-11-01

## 1. Context and goal

The pieces exist (ledger, backtest, battery, LLM layer); this spec turns them into the research desk: a
fixed sequence of agents that pre-registers a thesis, reproduces it, attacks it, explains the verdict and
stops for a person, recording every step in the ledger and surviving a restart while it waits.

## 2. User stories

- As a researcher, I want `qmas thesis run FILE` to take a thesis to a verdict and a memo, and stop.
- As the person accountable, I want to approve or reject it later, even after closing the terminal.

## 3. Applicable rules

`RULE-PREREG-01` (register node), `RULE-TRIALS-01` (quant records the trial; the red team deflates by the
family count), `RULE-LLM-01` and ADR 0002 (fixed routing, deterministic verdict), `RULE-AUDIT-01` (memo),
`RULE-HUMAN-01` (human gate).

## 4. Contracts and data model

- `DeskState`: thesis, stage, claimed Sharpe, report, memo and its source, decision, note.
- Stages: `received -> registered -> backtested -> judged -> reported -> decided`; a node that finds
  another stage raises `IllegalTransitionError`.
- LangGraph `StateGraph` with a SQLite checkpointer at `QMAS_DATA_DIR/checkpoints.sqlite3`; thread id =
  thesis key; the human gate uses `interrupt()` and is resumed with `Command(resume=...)`.
- A thesis key runs once; a new test needs a new version.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| CLI | `qmas thesis run FILE [--quick]` | Run to the human gate and print the verdict and memo. |
| CLI | `qmas thesis approve KEY [--note]` / `reject KEY [--note]` | Resume with a decision. |
| CLI | `qmas thesis status KEY` | Stage, verdict and what it waits for. |

## 6. Acceptance criteria

- [x] A thesis runs end to end, pauses at the human gate, and is resumed by a new process.
- [x] The ledger holds registration, trial, verdict and decision, and verifies.
- [x] An out-of-order node and a decision on a thesis that is not waiting both fail.
- [x] The LLM memo is replaced by the template when it quotes a number not in the evidence.
- [x] `uv run poe check` passes.

## 7. Required tests

Template memo, LLM memo accepted and rejected by the audit, allowed numbers, full run with restart,
illegal transitions, CLI lifecycle (run, status, approve, rerun refused, reject refused, unknown key).

## 8. Out of scope

- Correction rounds (`RULE-ROUNDS-01`) and the single holdout opening (`RULE-HOLDOUT-01`): the MVP stops at
  the design-window verdict; both come with the paper-trading spec.
- LLM-proposed attacks: spec 0012.

## Post-implementation notes

- Manual run of examples/theses/planted-momentum.yaml (quick): SURVIVES with a Sharpe ratio of 0.72,
  paused at the human gate, approved from a second process, ledger of 4 entries verified, rerun refused.
- `open_desk` closes the SQLite checkpointer; without it Python warns about unclosed databases.
