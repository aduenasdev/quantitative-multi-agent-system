# ADR 0003: LangGraph for agent orchestration

- **Status**: accepted
- **Date**: 2026-11-01

## Context

The agents (orchestrator, quant, red team, reporter, human gate) pass a typed state along a fixed workflow
with a conditional loop (at most two correction rounds) and a pause for human approval that must survive a
process restart.

Options considered: LangGraph, PydanticAI, CrewAI, AutoGen, a hand-written state machine.

## Decision

Use **LangGraph** (`>=1.0,<2`):

- `StateGraph` with a typed state and pure routing functions, so the workflow is explicit and testable.
- The red team is a subgraph that only receives the thesis and the results, never the author's narrative.
- `interrupt()` with a SQLite checkpointer for the human gate; resumed with `Command(resume=...)`.

CrewAI and AutoGen were rejected because their conversation-driven control flow makes decisions depend on
model output, which conflicts with [ADR 0002](0002-llms-propose-code-decides.md). A hand-written state
machine would need its own persistence and resume logic.

## Consequences

- One framework dependency in the core; nodes stay plain functions that can be tested without it.
- Checkpoints live in `QMAS_DATA_DIR`.
