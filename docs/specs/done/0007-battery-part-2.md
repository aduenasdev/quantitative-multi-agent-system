# Spec 0007: Red-team battery, part 2: robustness

- **Status**: done
- **Depends on**: 0006
- **Blocks**: 0008
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

Part one asks whether the edge is real at all. Part two asks whether it is the edge the thesis claims:
not a market bet in disguise, not one lucky period, not one lucky rebalancing day, not one name, and not
one bad price. Together they cover the ten planted defects of the evaluation plan.

## 2. User stories

- As the red team, I want each robustness attack to re-run the claim with one change, so that a failure
  points to one specific weakness.

## 3. Applicable rules

- `RULE-LLM-01`: deterministic attacks only.

## 4. Contracts and data model

| ID | Attack | Severity | Fails when (calibrated on calibration seeds 1000-1004) |
|---|---|---|---|
| A6 | Factor exposure: regress on the market factor | serious | alpha Sharpe < 0.5 x claimed, or the claim is significant but the alpha Newey-West t < 1.645 |
| A7 | Regime: three equal sub-periods | serious | a sub-period Sharpe <= 0, or one sub-period earns > 60 % of the PnL |
| A8 | Calendar: every other rebalancing offset | serious | mean Sharpe over the other offsets < 0.25 x claimed |
| A9 | Concentration: remove the top contributor | serious | top name > 50 % of the PnL, or Sharpe without it < 0.5 x claimed |
| A13 | Second price source | fatal | Sharpe gap > 0.1 + 0.2 x claimed |

Attacks are `INCONCLUSIVE` on claims without a positive Sharpe ratio, and A8 on daily rebalancing (a
single calendar).

## 5. Interfaces

| Kind | Name | Description |
|---|---|---|
| Python | `qmas.red_team.PART_TWO` | The attacks of this spec. |
| Python | `qmas.red_team.FULL_BATTERY` | Part one followed by part two. |

## 6. Acceptance criteria

- [x] Each attack fails on its planted defect (P10, P8, P9, P5, P7) and passes on a clean planted signal.
- [x] Thresholds come from `BatteryThresholds`.
- [x] `uv run poe check` passes.

## 7. Required tests

One test per attack: planted defect fails, clean signal passes, non-positive claim is inconclusive; A8 on
daily rebalancing is inconclusive; the full battery keeps the attack order.

## 8. Out of scope

- Fama-French factors on real data, A11 event days, A12 delay curve, A14 tails and A15-A19: spec 0013.

## Post-implementation notes

- A6 regresses on the synthetic market factor only; Fama-French and momentum factors on real data come
  with spec 0013.
- A9 and A13 judge PnL shares and source gaps rather than significance: one day can move an annualised
  Sharpe ratio by at most about sqrt(252 / T).
