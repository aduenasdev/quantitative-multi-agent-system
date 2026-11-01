# Spec 0002: Implement the statistics core

- **Status**: done
- **Depends on**: 0001
- **Blocks**: 0004-0008
- **Size**: M
- **Last updated**: 2026-11-01

## 1. Context and goal

Every red-team attack needs the same statistical tools: how likely a Sharpe ratio is to be real, how much
the best of many trials is inflated, whether a selection process overfits, confidence intervals that respect
overlapping returns, and false-discovery control across many tests. This spec implements them once, from
their textbook definitions, as pure NumPy/SciPy functions.

## 2. User stories

- As the red team, I want the deflated Sharpe ratio of a strategy given every trial of its family, so that
  selection bias is removed from the verdict.
- As the red team, I want the probability of backtest overfitting of a selection process, so that a
  strategy chosen from a grid can be rejected.
- As a researcher, I want bootstrap intervals that resample blocks, not single days, so that overlapping
  horizons do not shrink the intervals.

## 3. Applicable rules

- `RULE-TRIALS-01`: the deflated Sharpe ratio takes the number of trials and their Sharpe variance.

## 4. Contracts and data model

Pure functions over `numpy` arrays; no I/O. Sharpe ratios are **per period** (not annualised) unless the
name says otherwise. Kurtosis is the raw (non-excess) fourth standardised moment.

## 5. Interfaces

| Module | Functions | Source |
|---|---|---|
| `qmas.stats.sharpe` | `sharpe_ratio`, `annualised_sharpe_ratio`, `probabilistic_sharpe_ratio`, `expected_maximum_sharpe_ratio`, `deflated_sharpe_ratio`, `minimum_track_record_length` | Bailey and López de Prado (2012, 2014) |
| `qmas.stats.overfitting` | `probability_of_backtest_overfitting` (CSCV) | Bailey, Borwein, López de Prado and Zhu (2017) |
| `qmas.stats.bootstrap` | `moving_block_indices`, `block_bootstrap`, `paired_block_bootstrap`, `grouped_bootstrap`, `grouped_bootstrap_two_samples`, `one_sided_p_value`, `percentile_interval` | Künsch (1989) |
| `qmas.stats.multiple_testing` | `benjamini_hochberg` | Benjamini and Hochberg (1995) |
| `qmas.stats.information` | `cross_sectional_rank_ic`, `newey_west_t_statistic` | Grinold and Kahn (2000); Newey and West (1987) |
| `qmas.stats.cross_validation` | `purged_k_fold` | López de Prado (2018), chapter 7 |

## 6. Acceptance criteria

- [x] Every function above exists with type hints, a docstring citing its source and input validation.
- [x] Randomness only through an explicit `numpy.random.Generator`.
- [x] Tests use analytical special cases, Monte Carlo properties or invariants (see 7).
- [x] `uv run poe check` passes; coverage of `qmas.stats` is 95 % or more.

## 7. Required tests

- PSR with zero skewness and normal kurtosis equals the normal CDF of `(SR - SR*) * sqrt(n - 1)`.
- PSR is increasing in the observed Sharpe ratio and in the sample size.
- DSR with a single trial equals PSR against zero; DSR decreases as the number of trials grows.
- Expected maximum Sharpe ratio is close to the Monte Carlo maximum of normal draws.
- MinTRL inverts PSR: at `n = MinTRL`, PSR equals the requested confidence.
- PBO of pure-noise trials is close to 0.5; PBO with one strongly dominant trial is close to 0.
- Block bootstrap is reproducible from a seed and keeps blocks contiguous.
- Benjamini-Hochberg matches a hand-worked example and is monotone in `q`.
- Rank IC of a monotone transform of the returns is 1; Newey-West equals the plain t statistic with 0 lags.
- Purged k-fold: no training label window overlaps a test window, and the embargo is respected.

## 8. Out of scope

- Factor regressions and power analysis specific to attacks: specs 0006 and 0007.
- Pandas wrappers: callers convert to arrays.

## 9. Notes for the implementer

- The bootstrap functions port the block bootstrap of the earlier private research scripts, renamed to English.
- Euler-Mascheroni constant: use `numpy.euler_gamma`.

## 10. Post-implementation verification

- Each formula is checked against its paper by a reader, with the equation number in the docstring.

## Post-implementation notes

- `return_moments` was added to compute the Sharpe ratio, skewness and raw kurtosis in one call.
- The grouped bootstrap (whole calendar blocks) was added next to the moving-block bootstrap: it is what
  event studies need when several events share a block.
- ruff rules PLR0917 and PLR2004 are disabled project-wide: statistical signatures and minimum sample sizes
  read better without them.
