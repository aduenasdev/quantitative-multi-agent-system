from __future__ import annotations

import math

import numpy as np
import pytest

from qmas.stats.information import (
    cross_sectional_rank_ic,
    default_newey_west_lags,
    newey_west_t_statistic,
)


def test_rank_ic_of_monotone_transform_is_one() -> None:
    returns = np.random.default_rng(0).normal(0, 0.02, (12, 50))
    ic = cross_sectional_rank_ic(np.exp(returns * 10), returns)
    np.testing.assert_allclose(ic, 1.0)
    np.testing.assert_allclose(cross_sectional_rank_ic(-returns, returns), -1.0)


def test_rank_ic_handles_missing_and_constant_rows() -> None:
    returns = np.random.default_rng(1).normal(0, 0.02, (3, 30))
    signal = returns.copy()
    signal[0, 15:] = np.nan
    signal[1, :] = 1.0
    ic = cross_sectional_rank_ic(signal, returns, min_names=20)
    assert np.isnan(ic[0])
    assert np.isnan(ic[1])
    assert ic[2] == pytest.approx(1.0)


def test_rank_ic_rejects_mismatched_shapes() -> None:
    with pytest.raises(ValueError, match="same shape"):
        cross_sectional_rank_ic(np.zeros((2, 3)), np.zeros((3, 2)))


def test_newey_west_with_zero_lags_is_the_plain_t_statistic() -> None:
    series = np.random.default_rng(2).normal(0.1, 1.0, 400)
    expected = series.mean() / (series.std(ddof=0) / math.sqrt(series.size))
    assert newey_west_t_statistic(series, lags=0) == pytest.approx(expected)


def test_newey_west_shrinks_t_for_positively_autocorrelated_series() -> None:
    shocks = np.random.default_rng(3).normal(0.05, 1.0, 3000)
    smooth = np.convolve(shocks, np.ones(10) / 10, mode="valid")
    assert abs(newey_west_t_statistic(smooth, lags=20)) < abs(
        newey_west_t_statistic(smooth, lags=0)
    )


def test_newey_west_default_lags_and_validation() -> None:
    assert default_newey_west_lags(100) == 4
    series = np.random.default_rng(4).normal(0, 1, 100)
    assert newey_west_t_statistic(series) == pytest.approx(newey_west_t_statistic(series, lags=4))
    with pytest.raises(ValueError, match="three"):
        newey_west_t_statistic([1.0, 2.0])
    with pytest.raises(ValueError, match="lags"):
        newey_west_t_statistic(series, lags=100)
    with pytest.raises(ValueError, match="long-run"):
        newey_west_t_statistic([1.0, 1.0, 1.0], lags=0)
