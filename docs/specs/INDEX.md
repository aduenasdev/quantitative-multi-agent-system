# Spec index

Convention: [README.md](README.md). Template: [TEMPLATE.md](TEMPLATE.md).
Sizes: S < 1 day, M 1-3 days, L > 3 days.

## MVP (v0.1.0)

| # | Spec | Status | Size | Depends on | Blocks |
|---|---|---|---|---|---|
| 0001 | [Repository foundation](done/0001-repository-foundation.md) | done | M | none | all |
| 0002 | [Statistics core](done/0002-statistics-core.md) | done | M | 0001 | 0005-0008 |
| 0003 | [Thesis contract and hash-chained ledger](done/0003-thesis-and-ledger.md) | done | S | 0001 | 0010 |
| 0004 | [Synthetic market with planted bugs and signals](done/0004-synthetic-market.md) | done | M | 0002 | 0005-0008 |
| 0005 | [Cross-sectional backtest engine](done/0005-backtest-engine.md) | done | M | 0002, 0004 | 0006, 0007 |
| 0006 | [Red-team battery, part 1: leakage and overfitting](done/0006-battery-part-1.md) | done | M | 0005 | 0008 |
| 0007 | [Red-team battery, part 2: robustness](done/0007-battery-part-2.md) | done | M | 0006 | 0008 |
| 0008 | [E1 evaluation of the battery](done/0008-e1-evaluation.md) | done | M | 0006, 0007 | 0011 |
| 0008a | [E1 amendment 1: recalibrate A7 and A8](done/0008a-e1-amendment-1.md) | done | S | 0008 | 0011 |
| 0009 | [LLM layer: providers, cache, prompt registry, number audit](done/0009-llm-layer.md) | done | M | 0001 | 0010 |
| 0010 | [Agent graph with human approval, and CLI](done/0010-agent-graph.md) | done | L | 0003, 0006, 0009 | 0011 |
| 0011 | [Delivery: production image, README, architecture and research notes](done/0011-delivery.md) | done | M | 0008, 0010 | v0.1.0 |

## After the MVP

| # | Spec | Status |
|---|---|---|
| 0012 | LLM red team proposes attacks from closed templates (E2) | draft |
| 0013 | Complete battery (cemetery, factor data, remaining attacks) | draft |
| 0014 | Crypto thesis on public exchange data | draft |
| 0015 | SEC insider and 13F data | draft |
| 0016 | Port of the M1 catalyst event study | draft |
| 0017 | Knowledge base of retired theses | draft |
| 0018 | Technical analyst agent | draft |
