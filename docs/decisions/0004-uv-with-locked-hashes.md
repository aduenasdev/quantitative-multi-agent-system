# ADR 0004: uv with pinned dependencies and a hashed lock file

- **Status**: accepted
- **Date**: 2026-11-01

## Context

The system handles API keys for LLM providers and data vendors. A compromised dependency can read them
from the environment; this has happened to popular LLM gateway packages. Results must also be reproducible
months later.

## Decision

- [uv](https://docs.astral.sh/uv/) manages the environment. Dependencies are pinned exactly in
  `pyproject.toml` (`uv add --bounds exact`) and locked with hashes in `uv.lock`.
- Installs use `uv sync --locked`, locally and in Docker.
- Only packages that the code imports are declared.
- No LLM gateway library: the LLM client is a thin layer over the official provider SDKs.
- Upgrades are deliberate, one package at a time, with the checks run after each.

## Consequences

- A fresh clone reproduces the exact environment.
- Adding a dependency is an explicit, reviewable change to two files.
