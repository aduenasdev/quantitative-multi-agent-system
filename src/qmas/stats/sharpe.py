"""Sharpe ratio inference under non-normal returns and multiple testing.

References:
    Bailey, D. H. and López de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier."
        Journal of Risk 15(2). Probabilistic Sharpe ratio and minimum track record length.
    Bailey, D. H. and López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for
        Selection Bias, Backtest Overfitting and Non-Normality." Journal of Portfolio Management
        40(5).

All Sharpe ratios are per period (for example daily) unless a name says otherwise. Kurtosis is
the raw fourth standardised moment (3 for a normal distribution), not the excess kurtosis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats

NORMAL_KURTOSIS = 3.0


@dataclass(frozen=True)
class ReturnMoments:
    """Sample moments needed by the Sharpe inference functions."""

    sharpe_ratio: float
    skewness: float
    kurtosis: float
    n_observations: int


def _as_returns(returns: ArrayLike) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    if values.ndim != 1:
        raise ValueError("returns must be one-dimensional")
    values = values[np.isfinite(values)]
    if values.size < 2:
        raise ValueError("at least two finite returns are needed")
    if float(np.std(values, ddof=1)) == 0.0:
        raise ValueError("returns have zero variance")
    return values


def sharpe_ratio(returns: ArrayLike) -> float:
    """Return the per-period Sharpe ratio: mean over sample standard deviation.

    The returns are excess returns (the risk-free rate is already removed).
    """
    values = _as_returns(returns)
    return float(np.mean(values) / np.std(values, ddof=1))


def annualised_sharpe_ratio(returns: ArrayLike, periods_per_year: float) -> float:
    """Return the Sharpe ratio scaled by the square root of the number of periods per year."""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return sharpe_ratio(returns) * float(np.sqrt(periods_per_year))


def return_moments(returns: ArrayLike) -> ReturnMoments:
    """Return the Sharpe ratio, skewness, raw kurtosis and sample size of a return series."""
    values = _as_returns(returns)
    return ReturnMoments(
        sharpe_ratio=float(np.mean(values) / np.std(values, ddof=1)),
        skewness=float(stats.skew(values)),
        kurtosis=float(stats.kurtosis(values, fisher=False)),
        n_observations=int(values.size),
    )


def _sharpe_standard_error_factor(sr: float, skewness: float, kurtosis: float) -> float:
    """Return the Sharpe estimator variance factor 1 - skew * SR + (kurtosis - 1) / 4 * SR**2."""
    factor = 1.0 - skewness * sr + (kurtosis - 1.0) / 4.0 * sr**2
    if factor <= 0:
        raise ValueError("moments imply a non-positive Sharpe variance")
    return factor


def probabilistic_sharpe_ratio(
    observed_sr: float,
    benchmark_sr: float,
    n_observations: int,
    skewness: float = 0.0,
    kurtosis: float = NORMAL_KURTOSIS,
) -> float:
    """Return the probability that the true Sharpe ratio exceeds ``benchmark_sr``.

    Bailey and López de Prado (2012):

    PSR = Phi((SR - SR*) * sqrt(n - 1) / sqrt(1 - skew * SR + (kurt - 1) / 4 * SR**2)).
    """
    if n_observations < 2:
        raise ValueError("n_observations must be at least 2")
    factor = _sharpe_standard_error_factor(observed_sr, skewness, kurtosis)
    z = (observed_sr - benchmark_sr) * np.sqrt(n_observations - 1) / np.sqrt(factor)
    return float(stats.norm.cdf(z))


def expected_maximum_sharpe_ratio(n_trials: int, trials_sr_variance: float) -> float:
    """Return the expected maximum Sharpe ratio of ``n_trials`` trials with zero true Sharpe.

    Bailey and López de Prado (2014), equation for SR0:
    sqrt(V) * ((1 - gamma) * Phi^-1(1 - 1/N) + gamma * Phi^-1(1 - 1/(N e))),
    with gamma the Euler-Mascheroni constant. With a single trial there is no selection: 0.
    """
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")
    if trials_sr_variance < 0:
        raise ValueError("trials_sr_variance must be non-negative")
    if n_trials == 1:
        return 0.0
    gamma = float(np.euler_gamma)
    quantiles = (1.0 - gamma) * stats.norm.ppf(1.0 - 1.0 / n_trials) + gamma * stats.norm.ppf(
        1.0 - 1.0 / (n_trials * np.e)
    )
    return float(np.sqrt(trials_sr_variance) * quantiles)


def deflated_sharpe_ratio(
    observed_sr: float,
    n_observations: int,
    n_trials: int,
    trials_sr_variance: float,
    skewness: float = 0.0,
    kurtosis: float = NORMAL_KURTOSIS,
) -> float:
    """Return the probabilistic Sharpe ratio against the expected maximum of the trials (DSR).

    Rule: RULE-TRIALS-01. ``n_trials`` counts every trial of the family, not only the last one.
    """
    benchmark = expected_maximum_sharpe_ratio(n_trials, trials_sr_variance)
    return probabilistic_sharpe_ratio(observed_sr, benchmark, n_observations, skewness, kurtosis)


def minimum_track_record_length(
    observed_sr: float,
    benchmark_sr: float,
    skewness: float = 0.0,
    kurtosis: float = NORMAL_KURTOSIS,
    confidence: float = 0.95,
) -> float:
    """Return the number of observations needed for PSR to reach ``confidence``.

    Bailey and López de Prado (2012):
    MinTRL = 1 + (1 - skew * SR + (kurt - 1) / 4 * SR**2) * (z_confidence / (SR - SR*))**2.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if observed_sr <= benchmark_sr:
        raise ValueError("observed_sr must exceed benchmark_sr")
    factor = _sharpe_standard_error_factor(observed_sr, skewness, kurtosis)
    z = float(stats.norm.ppf(confidence))
    return float(1.0 + factor * (z / (observed_sr - benchmark_sr)) ** 2)
