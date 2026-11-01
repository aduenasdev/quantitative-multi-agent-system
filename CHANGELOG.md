# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Repository foundation (spec 0001): packaging with uv, ruff, mypy strict, pytest with coverage, typed
  settings, logging, CLI skeleton, repository check, spec convention, governance rules, ADRs 0001-0004,
  local Docker environment and pre-commit hooks.
- Statistics core (spec 0002): probabilistic and deflated Sharpe ratio, minimum track record length,
  probability of backtest overfitting (CSCV), block and grouped bootstrap, Benjamini-Hochberg, rank IC,
  Newey-West t statistic and purged k-fold with embargo.
- Thesis contract and hash-chained ledger (spec 0003): YAML theses with a content hash, tamper-evident ledger, pre-registration rule, `qmas thesis validate` and `qmas ledger verify`.
- Synthetic market (spec 0004): factor model with fat tails, delistings, clock-time events, planted characteristic of known rank IC, market-level defect knobs and a signal registry.
