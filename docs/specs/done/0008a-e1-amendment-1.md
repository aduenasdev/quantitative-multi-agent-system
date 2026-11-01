# Spec 0008a: E1 amendment 1, recalibrate A7 and A8

- **Status**: done
- **Depends on**: 0008
- **Blocks**: 0011
- **Size**: S
- **Last updated**: 2026-11-01

## 1. Context and goal

E1 run 1 (judgement seeds 2000-2004) failed its third criterion: only 5 of 10 detectable planted signals
survived. A8 (calendar) and A7 (regime) rejected real signals because their statistics were ratios of
two noisy Sharpe ratios, with thresholds tuned on five calibration seeds per level. A calibration study on
20 calibration seeds (1000-1019) showed it:

| Statistic (20 calibration seeds) | IC 0.04 | IC 0.08 | Defect it targets |
|---|---|---|---|
| Median claimed Sharpe | 1.07 | 2.70 | |
| Best sub-period share of PnL > 0.6 | 7 / 20 | 0 / 20 | P8: 20 / 20 |
| Best sub-period share of PnL > 0.9 | 2 / 20 | 0 / 20 | P8: 18 / 20 |
| Some sub-period Sharpe <= 0 | 5 / 20 | 0 / 20 | P8: 18 / 20 |
| Other-calendar Sharpe retention < 0.25 | 10 / 20 | 2 / 20 | P9: 20 / 20 |
| Mean other-calendar Sharpe <= 0 | 4 / 20 | 0 / 20 | P9: 17 / 20; A1 catches P9 in 20 / 20 |

## 2. Amendment (dated 2026-11-01)

1. A7 fails only when one sub-period earns more than 90 % of the PnL. A weak but real signal often has one
   losing sub-period, so "some sub-period Sharpe <= 0" is dropped.
2. A8 fails when the mean Sharpe ratio over the other calendars is not positive (the edge disappears away
   from its rebalancing day). The retention ratio stays as a reported metric.
3. Calibration seeds widen to 1000-1019. The expected Sharpe ratio of each planted level is estimated
   on all 20 of them.
4. The three E1 criteria do not change.
5. Judgement seeds 2000-2004 are retired. Run 2 uses 3000-3004, once, after this amendment is merged.

## 3. Acceptance criteria

- [x] Thresholds and seeds changed as above; tests updated.
- [x] Run 2 executed once on seeds 3000-3004 and published with run 1 in `docs/research/e1-results.md`.
- [x] `uv run poe check` passes.

## 4. Out of scope

- Further changes after run 2, whatever its result: they would need amendment 2 and new seeds.

## Post-implementation notes

- Run 2 on judgement seeds 3000-3004 PASSED: defects 46/47, noise 0/5, detectable signals 9/10. One P8
  case survived. Published in docs/research/e1-run-2.md and summarised in docs/research/e1-results.md.
