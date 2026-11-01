# ADR 0002: Language models propose, deterministic code decides, a person approves

- **Status**: accepted
- **Date**: 2026-11-01

## Context

The system judges whether a trading hypothesis survives a red team. Large language models are good at
proposing attacks, explaining results and writing reports. They are also non-deterministic, they can invent
numbers, and many of them have seen the market history they would be asked to judge.

## Decision

- Every verdict is computed by deterministic, tested code: the red-team battery and its aggregation rules.
- Agents backed by an LLM may propose extra attacks, explain results and draft the report. They may add
  attacks or lower confidence, never raise it (`RULE-LLM-01`).
- Every number in an LLM-written report must be traced to a stored result; otherwise the report is replaced
  by a deterministic template (`RULE-AUDIT-01`).
- Orchestration is a deterministic state machine, not an LLM supervisor.
- Promotion of a thesis requires an explicit human approval recorded in the ledger (`RULE-HUMAN-01`).
- The whole system runs without any LLM key in a `simulated` mode with the same interfaces.

## Consequences

- Results are reproducible from a seed, with or without an LLM.
- The LLM layer can be evaluated separately: does it find defects the battery misses, and at what cost?
- The system is less "autonomous" than a free-form agent loop, on purpose.
