# E1 results: does the red team catch planted defects without killing real signals?

E1 runs the full battery on cases whose truth is known (ten planted defects and five planted signal
strengths, on five seeds each) and checks three criteria fixed before the run. Every run is published,
including the failed ones. Seeds used for a verdict are never reused.

| Run | Judgement seeds | Thresholds | Defects caught (>= 95 %) | Noise surviving (<= 10 %) | Detectable signals surviving (>= 80 %) | Result |
|---|---|---|---|---|---|---|
| [1](e1-run-1.md) | 2000-2004 | calibrated on seeds 1000-1004 | 46 / 46 (100 %) | 0 / 5 (0 %) | 5 / 10 (50 %) | **failed** |
| [2](e1-run-2.md) | 3000-3004 | amendment 1, calibrated on seeds 1000-1019 | 46 / 47 (98 %) | 0 / 5 (0 %) | 9 / 10 (90 %) | **passed** |

"Detectable" means planted rank IC 0.04 and 0.08: their expected Sharpe ratio is above the minimum
detectable Sharpe ratio of the six-year design window (1.00 at 95 % confidence and 80 % power). A defect
case whose claimed Sharpe ratio is not positive is not a claim anyone would bring; it is reported and left
out of the first criterion (4 cases in run 1, 3 in run 2).

## Run 1

The battery caught every defect claim and let no noise through, but it was too strict with real signals:
A8 (rebalancing calendar) and A7 (sub-period regime) rejected half of the planted signals with rank IC
0.04 and 0.08. Their statistics were ratios of two noisy Sharpe ratios, with thresholds tuned on five
calibration seeds per level.

## Amendment 1

A calibration study on 20 calibration seeds (never on the judgement seeds) changed two rules
([spec 0008a](../specs/done/0008a-e1-amendment-1.md)):

- A7 fails when one sub-period earns more than 90 % of the PnL (it used to also fail on any losing
  sub-period, which weak real signals often have);
- A8 fails when the mean Sharpe ratio over the other rebalancing calendars is not positive (it used to
  compare a ratio with 0.25).

## Run 2

All three criteria pass. What it still gets wrong:

- **One missed defect.** A P8 case (a signal that only works in 2020-2021) survived on seed 3004: its
  best sub-period earned less than 90 % of the PnL because the inactive years were slightly positive by
  chance.
- **Weak real signals are mostly rejected or unprovable.** Planted rank IC 0.01 and 0.02 sit below the
  detectable Sharpe ratio of six years of data; the battery calls most of them `NOT_PROVABLE` or
  `WOUNDED`. This is the price of a 0 % false positive rate on noise.
- **The synthetic half only.** The evaluation plan also asks for known nulls, validated strategies and
  real bugs on real data. Those need data that cannot be redistributed and are not part of this
  repository.
