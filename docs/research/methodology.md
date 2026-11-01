# Methodology

The project follows one discipline, borrowed from clinical trials and from the backtest-overfitting
literature: **decide how a hypothesis will be judged before looking at the result, and publish the result
whatever it is.**

## A thesis is pre-registered

A thesis (YAML) states the hypothesis, the data, the signal, the portfolio, the horizon, the design and
holdout windows, the costs and the pass thresholds. Its SHA-256 goes to the ledger before the first
backtest (`RULE-PREREG-01`). A change of any field is a new version and a new trial (`RULE-TRIALS-01`).

## Every trial counts

Selecting the best of N trials inflates the Sharpe ratio. The deflated Sharpe ratio (Bailey and López de
Prado, 2014) compares the claim with the expected maximum of N trials. CSCV (Bailey, Borwein, López de
Prado and Zhu, 2017) gives the probability that the in-sample winner is below the median out of sample.
The ledger keeps the count per family, so deflation uses every trial, not only the reported one.

## The red team attacks one weakness at a time

Each attack re-runs the claim with one switch flipped, or computes one statistic, and returns `PASSED`,
`FAILED` or `INCONCLUSIVE`. Attacks that test whether an edge survives a change are inconclusive when the
claim has no positive edge. Verdict rules, in order: a failed fatal attack gives `BROKEN`; a failed
serious attack gives `WOUNDED`; a claim that is not significant gives `NOT_PROVABLE`; otherwise
`SURVIVES`. `SURVIVES` means "no known defect found", not "edge proven".

## The red team is evaluated too (E1)

The synthetic market plants signals of known rank IC (0, 0.01, 0.02, 0.04, 0.08) and ten defects
(look-ahead, survivorship, gross-only edge, selection among 200 noise signals, a single-name jump, a
time-zone error, a bad price, a regime-limited signal, a single-calendar signal, a disguised market bet).

- **Seeds.** Thresholds are tuned on calibration seeds. The verdict is given on judgement seeds that
  nothing was tuned on.
- **Criteria, fixed before the run:** at least 95 % of defect claims caught, at most 10 % of noise
  surviving, at least 80 % of detectable real signals surviving.
- **If E1 fails**, the thresholds change only through a dated amendment. The new thresholds are
  calibrated on calibration seeds and judged on new judgement seeds. Used seeds are retired.

Run 1 failed and was published; amendment 1 followed; run 2 passed
([e1-results.md](e1-results.md)).

## Statistics

| Tool | Reference |
|---|---|
| Probabilistic Sharpe ratio, minimum track record length | Bailey and López de Prado (2012) |
| Deflated Sharpe ratio | Bailey and López de Prado (2014) |
| Probability of backtest overfitting (CSCV) | Bailey, Borwein, López de Prado and Zhu (2017) |
| Purged k-fold cross-validation with embargo | López de Prado (2018), chapter 7 |
| Moving-block bootstrap | Künsch (1989) |
| False discovery rate | Benjamini and Hochberg (1995) |
| Information coefficient | Grinold and Kahn (2000) |
| Autocorrelation-robust t statistic | Newey and West (1987) |
| Overlapping holding-period portfolios | Jegadeesh and Titman (1993) |

Tests use analytical special cases (for example, PSR under normality is a normal CDF), Monte Carlo
properties (PBO of pure noise is about one half) and invariants, never figures copied from memory.
