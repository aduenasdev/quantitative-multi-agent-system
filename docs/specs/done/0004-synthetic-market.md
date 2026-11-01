# Spec 0004: Generate a synthetic market with planted signals and defects

- **Status**: done
- **Depends on**: 0002
- **Blocks**: 0005-0008
- **Size**: L
- **Last updated**: 2026-11-01

## 1. Context and goal

To know whether the red team works, it must be tested on cases whose truth is known: signals of a known
strength and theses with exactly one planted defect. Real data cannot provide that, and it carries
licences. This spec builds a synthetic daily equity market that is hard enough to be realistic (factor
structure, fat tails, volatility clustering, delistings, an event calendar with clock times, costs that
depend on volatility) and exposes the knobs that plant each signal and defect.

## 2. User stories

- As the E1 evaluation, I want a market with a planted characteristic of known rank IC, so that I can measure
  how often the battery accepts real signals and rejects noise.
- As the E1 evaluation, I want market-level defects (survivor-dependent delistings, a single-name jump, a
  bad price in one data source, a regime-limited or front-loaded signal, a gross-only reversal effect, and
  events with clock times), so that each planted defect has something real to hide behind.

## 3. Applicable rules

- `RULE-DATA-01`: synthetic data is generated on demand from a seed and never committed.

## 4. Contracts and data model

`MarketConfig` (frozen dataclass, all defaults realistic) and `SyntheticMarket`:

| Field | Shape | Meaning |
|---|---|---|
| `dates` | T | Business days (`datetime64[D]`). |
| `returns` | T x N | Daily simple returns of the primary data source; NaN after delisting. |
| `secondary_returns` | T x N | A second, independent source: equal to `returns` except for injected data errors. |
| `alive` | T x N | Whether the asset can be traded at the close of day t. |
| `delisting_day` | N | Index of the delisting day (return `delisting_return`), or -1. |
| `market_factor`, `betas`, `sectors`, `idio_vol`, `cost_bps` | T, N, N, N, N | Factor structure and per-name one-way cost, proportional to volatility. |
| `characteristic` | T x N | Planted characteristic, constant within each block of `signal_horizon` days and known at the block start. |
| `events` | structured array | Asset, day, local New York clock time (minutes), surprise, reaction day. |
| `block_starts` | B | Day index of each block start (the signal grid). |

Planted strength: in every block the characteristic is scaled so that its cross-sectional correlation
with the block's forward return equals `planted_ic` in expectation.

Market-level defect knobs: `signal_active_years` (P8), `signal_front_loaded` (P9), `reversal_strength`
(P3), `delisting_loser_sensitivity` (P2), `jump_size` (P5), `price_error_size` (P7) and the event clock
(P6). Strategy-level defects (P1, P4, P6, P10) live in the signals.

Signal registry `qmas.market.signals`: `planted_characteristic`, `future_return`, `short_term_reversal`,
`trailing_return`, `random_characteristic`, `beta_exposure`, `event_surprise`. Each maps a market and its
parameters to a T x N matrix whose row t is what the signal claims to know at the close of day t.

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.market.generate_market(config, seed)` | Build a `SyntheticMarket`. |
| Python | `qmas.market.signals.compute_signal(name, market, parameters)` | Evaluate a registered signal. |

## 6. Acceptance criteria

- [x] Same seed, same market; different seed, different market.
- [x] Pooled daily stock returns have kurtosis above 5; two disjoint random equal-weight baskets of 40 names
      correlate between 0.8 and 0.95, as large-cap baskets do.
- [x] Delisted assets return `delisting_return` on their last day and NaN afterwards; losers delist more.
- [x] The measured rank IC of the characteristic matches `planted_ic` within tolerance, including 0.
- [x] Each defect knob changes only what it should (checked by a test per knob).
- [x] Unknown signal names fail with a clear error; signals never read data from after their row.
      Exception, on purpose: `future_return` (the look-ahead defect P1).
- [x] Generating the default market takes under two seconds.

## 7. Required tests

One test per criterion above, plus: event reactions land on the right day for pre-open, intraday and
after-close events; `event_surprise` with `timestamps_as_utc` reveals after-close events one day early.

## 8. Out of scope

- Portfolio construction and costs in the backtest: spec 0005.
- The E1 case library that combines market knobs and strategies: spec 0008.

## 9. Notes for the implementer

- Requirements come from the evaluation plan of the battery: basket correlation, fat tails, negative
  delisting returns, clock-time events, volatility-dependent costs, and seeds for calibration kept apart
  from seeds for judgement.
- The time-zone defect P6: a vendor gives New York local times; buggy code treats them as UTC and converts
  them to New York, which moves after-close events into the trading day.

## Post-implementation notes

- The evaluation plan asked for baskets correlated at
