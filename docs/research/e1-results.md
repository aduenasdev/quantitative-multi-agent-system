# E1 results: does the red team catch planted defects without killing real signals?

E1 runs the full battery on cases whose truth is known (ten planted defects and five planted signal
strengths, on five seeds each) and checks three criteria fixed before the run. Every run is published,
including the failed ones.

| Run | Date | Judgement seeds | Thresholds | Defects caught (>= 95 %) | Noise surviving (<= 10 %) | Detectable signals surviving (>= 80 %) | Result |
|---|---|---|---|---|---|---|---|
| [1](e1-run-1.md) | 2026-11-01 | 2000-2004 | calibrated on seeds 1000-1004 | 46 / 46 (100 %) | 0 / 5 (0 %) | 5 / 10 (50 %) | **failed** |

## Run 1

The battery caught every defect claim and let no noise through, but it was too strict with real signals:
A8 (rebalancing calendar) and A7 (sub-period regime) rejected half of the planted signals with rank IC
0.04 and 0.08. Their thresholds had been tuned on five calibration seeds per level, which was too few: the
spread of those statistics across seeds is wider than five draws showed.

Following the evaluation protocol, the thresholds are not tuned on seeds 2000-2004. Amendment 1
recalibrates A7 and A8 on a larger calibration set and E1 is repeated on new judgement seeds.
