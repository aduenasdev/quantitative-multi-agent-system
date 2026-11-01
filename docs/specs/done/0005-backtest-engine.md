# Spec 0005: Build the cross-sectional backtest engine

- **Status**: done
- **Depends on**: 0002, 0003, 0004
- **Blocks**: 0006, 0007
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

The quant agent needs to reproduce what a thesis claims, and the red team needs to re-run it with one thing
changed: a day of delay, a point-in-time universe, realistic costs, another price source, a name removed,
another rebalancing day. This spec builds one deterministic engine with those switches as explicit
parameters of a `StrategySpec`.

## 2. User stories

- As the quant agent, I want to turn a thesis into a strategy and a market, and get daily gross and net
  returns, turnover and per-name contributions.
- As the red team, I want to change a single switch of the strategy and re-run it, so that the difference
  measures one suspected defect.

## 3. Applicable rules

- `RULE-DATA-01`: the engine only reads the in-memory market; nothing is written.

## 4. Contracts and data model

`StrategySpec` (frozen): `signal`, `signal_parameters`, `horizon_days`, `rebalance_every_days`, `offset`,
`portfolio` (`long_short` or `long_only`), `quantile`, `universe` (`point_in_time` or `survivors`),
`execution_delay`, `price_source` (`primary` or `secondary`), `cost_model` (`flat` or `per_name`),
`cost_bps`, `excluded_assets`, `start`, `end`.

Mechanics (standard overlapping-portfolio design of Jegadeesh and Titman, 1993): on each rebalancing day
`d` the signal row `d` ranks the names tradable at `d`; the top (and, for long-short, the bottom)
`quantile` get equal weights; the trade happens `execution_delay` days after the close of `d`; the
tranche is held for `horizon_days` with constant weights and
carries `rebalance_every_days / horizon_days` of the capital. Costs are charged on the turnover of each
tranche: `flat` uses `cost_bps` for every name, `per_name` uses the market's volatility-dependent costs.
A delisted name returns its delisting return and then nothing.

`Thesis` gains `portfolio: {kind, quantile}` (default long-short quintiles).

`BacktestResult`: `dates`, `gross_returns`, `net_returns`, `turnover`, `contributions`, `n_rebalances`,
`average_names`, and `sharpe(net=True)` annualised over 252 days.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.backtest.run_backtest(market, strategy)` | Run a strategy on a market. |
| Python | `qmas.backtest.strategy_from_thesis(thesis, window)` | Strategy for the design or holdout window. |
| Python | `qmas.backtest.market_from_thesis(thesis)` | Generate the market a thesis names. |

## 6. Acceptance criteria

- [x] Long-short weights sum to zero with gross exposure two; long-only weights sum to one.
- [x] A planted IC of 0.08 gives a clearly positive Sharpe; a planted IC of 0 gives about zero on average.
- [x] Each switch changes only what it should (one test per switch).
- [x] `horizon_days` not a multiple of `rebalance_every_days` is rejected.
- [x] A full design-window backtest of 200 names runs in well under a second.
- [x] `uv run poe check` passes.

## 7. Required tests

One test per criterion and per switch; overlapping tranches (horizon 21, rebalancing every 7 days);
returns outside the window are never used; costs equal turnover times cost.

## 8. Out of scope

- Short-selling costs, borrow availability and market impact beyond a linear cost.
- Weights drifting with prices inside a holding period (weights are held constant).

## Post-implementation notes

- `execution_delay` first meant use
