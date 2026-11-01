# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-01

### Added

- Repository foundation (spec 0001): packaging with uv, ruff, mypy strict, pytest with coverage, typed
  settings, logging, CLI skeleton, repository check, spec convention, governance rules, ADRs 0001-0004,
  local Docker environment and pre-commit hooks.
- Statistics core (spec 0002): probabilistic and deflated Sharpe ratio, minimum track record length,
  probability of backtest overfitting (CSCV), block and grouped bootstrap, Benjamini-Hochberg, rank IC,
  Newey-West t statistic and purged k-fold with embargo.
- Thesis contract and hash-chained ledger (spec 0003): YAML theses with a content hash, tamper-evident ledger, pre-registration rule, `qmas thesis validate` and `qmas ledger verify`.
- Synthetic market (spec 0004): factor model with fat tails, delistings, clock-time events, planted characteristic of known rank IC, market-level defect knobs and a signal registry.
- Backtest engine (spec 0005): overlapping long-short or long-only portfolios with switches for delay, universe, price source, costs, excluded names and rebalancing offset.
- Red-team battery, part one (spec 0006): verdicts and attacks A1-A5 and A10 with pre-registered thresholds.
- Red-team battery, part two (spec 0007): attacks A6-A9 and A13, and the full battery.
- E1 evaluation (spec 0008): case library, criteria, report and `qmas evaluate e1`; run 1 published (failed: too strict with real signals).
- E1 amendment 1 (spec 0008a): A7 and A8 recalibrated on 20 calibration seeds; run 2 on new judgement
  seeds passes every criterion.
- LLM layer (spec 0009): OpenAI, Anthropic, xAI and OpenAI-compatible providers, simulated mode, exact cache, spending caps, locked prompts and number audit.
- Agent graph (spec 0010): orchestrator, quant, red team, reporter and human gate in LangGraph, with `qmas thesis run|approve|reject|status`.
- Delivery (spec 0011): production Docker image and `compose.prod.yml`, complete README, architecture
  and research notes.
