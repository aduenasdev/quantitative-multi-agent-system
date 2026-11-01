# Quantitative Multi-Agent System

A multi-agent research desk that tries to **break** quantitative trading hypotheses before anyone trusts them.
Language-model agents propose and explain; deterministic code decides; a person approves.

> **Status: work in progress (pre-v0.1.0).** The repository is being built spec by spec; see
> [docs/specs/INDEX.md](docs/specs/INDEX.md). This README is completed with the v0.1.0 release.

## Why

Most backtests that look good are wrong in a few predictable ways: look-ahead leakage, survivorship bias,
ignored trading costs, and above all trying many ideas and reporting only the best one. This project turns
those failure modes into an automated red team with a pre-registered evaluation, and publishes its error
rates whatever they turn out to be.

## Quick start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/), or Docker.

```bash
uv sync
cp .env.example .env        # optional: every variable has a safe default
uv run qmas --version
uv run poe check            # lint, format, types, tests, repository check
```

With Docker:

```bash
docker compose run --rm dev poe check
```

## Project rules

- Governance rules for testing a thesis: [docs/rules.md](docs/rules.md).
- Contributor and coding rules: [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
- Architecture decisions: [docs/decisions/](docs/decisions/).

## Disclaimer

Research software for education. It is not investment advice and does not trade real money.

## License

[MIT](LICENSE)
