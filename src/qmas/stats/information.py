"""Information coefficient and autocorrelation-robust inference.

References:
    Grinold, R. C. and Kahn, R. N. (2000). Active Portfolio Management, 2nd ed. McGraw-Hill.
        Information coefficient as the cross-sectional correlation of forecasts and outcomes.
    Newey, W. K. and West, K. D. (1987). "A Simple, Positive Semi-Definite, Heteroskedasticity and
        Autocorrelation Consistent Covariance Matrix." Econometrica 55(3).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats


def cross_sectional_rank_ic(
    signal: ArrayLike, forward_returns: ArrayLike, min_names: int = 20
) -> np.ndarray:
    """Return the Spearman correlation of signal and forward return, one value per period.

    Both inputs have shape (n_periods, n_assets); missing values are NaN. Periods with fewer than
    ``min_names`` assets having both values, or with a constant signal, give NaN.
    """
    x = np.asarray(signal, dtype=float)
    y = np.asarray(forward_returns, dtype=float)
    if x.shape != y.shape or x.ndim != 2:
        raise ValueError("signal and forward_returns must be 2-D arrays of the same shape")
    result = np.full(x.shape[0], np.nan)
    for row in range(x.shape[0]):
        valid = np.isfinite(x[row]) & np.isfinite(y[row])
        if valid.sum() < min_names:
            continue
        xs, ys = x[row, valid], y[row, valid]
        if np.ptp(xs) == 0 or np.ptp(ys) == 0:
            continue
        result[row] = np.corrcoef(stats.rankdata(xs), stats.rankdata(ys))[0, 1]
    return result


def default_newey_west_lags(n_observations: int) -> int:
    """Return the rule-of-thumb lag length: floor(4 * (n / 100) ** (2 / 9))."""
    scaled: float = (n_observations / 100.0) ** (2.0 / 9.0)
    return math.floor(4.0 * scaled)


def newey_west_t_statistic(series: ArrayLike, lags: int | None = None) -> float:
    """Return the t statistic of the mean of ``series`` with a Newey-West standard error.

    The long-run variance uses the Bartlett kernel.

    With ``lags=0`` this is the mean over the population standard deviation divided by sqrt(n).
    """
    values = np.asarray(series, dtype=float)
    values = values[np.isfinite(values)]
    n = values.size
    if n < 3:
        raise ValueError("need at least three finite observations")
    lag_count = default_newey_west_lags(n) if lags is None else lags
    if not 0 <= lag_count < n:
        raise ValueError("lags must be in [0, n)")
    centred = values - values.mean()
    long_run_variance = float(centred @ centred) / n
    for lag in range(1, lag_count + 1):
        weight = 1.0 - lag / (lag_count + 1)
        autocovariance = float(centred[lag:] @ centred[:-lag]) / n
        long_run_variance += 2.0 * weight * autocovariance
    if long_run_variance <= 0:
        raise ValueError("non-positive long-run variance")
    return float(values.mean() / math.sqrt(long_run_variance / n))
