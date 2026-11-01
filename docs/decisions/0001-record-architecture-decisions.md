# ADR 0001: Record architecture decisions

- **Status**: accepted
- **Date**: 2026-11-01

## Context

The project is built spec by spec, often with AI coding agents. Decisions that are not written down get
re-discussed or silently reversed.

## Decision

Architecture decisions are recorded as short ADRs in `docs/decisions/`, in the
[MADR](https://adr.github.io/madr/) style: context, decision, consequences. Files are numbered
`NNNN-title.md`; numbers are never reused. An accepted ADR is not edited: a new ADR supersedes it.

## Consequences

- Every non-obvious choice has a findable reason.
- Specs cite ADRs instead of repeating the reasoning.
