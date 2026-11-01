from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy import stats

from qmas.stats.sharpe import (
    annualised_sharpe_ratio,
    deflated_sharpe_ratio,
    expected_maximum_sharpe_ratio,
    minimum_track_record_length,
    probabilistic_sharpe_ratio,
    return_moments,
    sharpe_ratio,
)


def test_sharpe_ratio_of_known_series() -> None:
    returns = np.array([0.01, 0.03, -0.01, 0.01])
    assert sharpe_ratio(returns) == pytest.approx(0.01 / np.std(returns, ddof=1))
    assert annualised_sharpe_ratio(returns, 252) == pytest.approx(
        sharpe_ratio(returns) * math.sqrt(252)
    )


def test_sharpe_ratio_ignores_nan_and_rejects_degenerate_input() -> None:
    assert sharpe_ratio([0.01, np.nan, 0.03]) == pytest.approx(sharpe_ratio([0.01, 0.03]))
    with pytest.raises(ValueError, match="zero variance"):
        sharpe_ratio([0.01, 0.01, 0.01])
    with pytest.raises(ValueError, match="two finite"):
        sharpe_ratio([0.01])
    with pytest.raises(ValueError, match="one-dimensional"):
        sharpe_ratio([[0.01, 0.02]])
    with pytest.raises(ValueError, match="positive"):
        annualised_sharpe_ratio([0.01, 0.02], 0)


def test_return_moments_of_normal_sample() -> None:
    rng = np.random.default_rng(1)
    moments = return_moments(rng.normal(0.001, 0.01, 200_000))
    assert moments.skewness == pytest.approx(0.0, abs=0.02)
    assert moments.kurtosis == pytest.approx(3.0, abs=0.05)
    assert moments.sharpe_ratio == pytest.approx(0.1, abs=0.01)
    assert moments.n_observations == 200_000


@given(
    sr=st.floats(-0.5, 0.5),
    benchmark=st.floats(-0.5, 0.5),
    n=st.integers(2, 5000),
)
def test_psr_reduces_to_normal_cdf_under_normality(sr: float, benchmark: float, n: int) -> None:
    factor = 1 + sr**2 / 2
    expected = stats.norm.cdf((sr - benchmark) * math.sqrt(n - 1) / math.sqrt(factor))
    assert probabilistic_sharpe_ratio(sr, benchmark, n) == pytest.approx(expected)


def test_psr_is_monotone_in_sharpe_and_sample_size() -> None:
    assert probabilistic_sharpe_ratio(0.10, 0, 250) > probabilistic_sharpe_ratio(0.05, 0, 250)
    assert probabilistic_sharpe_ratio(0.05, 0, 1000) > probabilistic_sharpe_ratio(0.05, 0, 250)
    assert probabilistic_sharpe_ratio(0.05, 0.05, 250) == pytest.approx(0.5)


def test_psr_penalises_negative_skew_and_fat_tails() -> None:
    normal = probabilistic_sharpe_ratio(0.1, 0, 250)
    assert probabilistic_sharpe_ratio(0.1, 0, 250, skewness=-1.0, kurtosis=8.0) < normal


def test_psr_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        probabilistic_sharpe_ratio(0.1, 0, 1)
    with pytest.raises(ValueError, match="non-positive"):
        probabilistic_sharpe_ratio(2.0, 0, 100, skewness=5.0, kurtosis=1.0)


def test_expected_maximum_matches_monte_carlo() -> None:
    rng = np.random.default_rng(7)
    n_trials, variance = 100, 0.04
    maxima = rng.normal(0, math.sqrt(variance), (20_000, n_trials)).max(axis=1)
    assert expected_maximum_sharpe_ratio(n_trials, variance) == pytest.approx(
        maxima.mean(), rel=0.03
    )
    assert expected_maximum_sharpe_ratio(1, variance) == 0.0


def test_expected_maximum_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="n_trials"):
        expected_maximum_sharpe_ratio(0, 0.1)
    with pytest.raises(ValueError, match="non-negative"):
        expected_maximum_sharpe_ratio(10, -0.1)


def test_dsr_with_one_trial_is_psr_against_zero() -> None:
    assert deflated_sharpe_ratio(0.08, 500, 1, 0.01) == pytest.approx(
        probabilistic_sharpe_ratio(0.08, 0.0, 500)
    )


def test_dsr_decreases_with_more_trials() -> None:
    values = [deflated_sharpe_ratio(0.08, 500, n, 0.001) for n in (1, 10, 100, 1000)]
    assert values == sorted(values, reverse=True)
    assert values[-1] < values[0]


@given(
    sr=st.floats(0.02, 0.5),
    skew=st.floats(-1.0, 1.0),
    kurt=st.floats(3.0, 10.0),
    confidence=st.floats(0.6, 0.99),
)
def test_min_trl_inverts_psr(sr: float, skew: float, kurt: float, confidence: float) -> None:
    n = minimum_track_record_length(sr, 0.0, skew, kurt, confidence)
    psr_at_n = stats.norm.cdf(
        sr * math.sqrt(n - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    )
    assert psr_at_n == pytest.approx(confidence)


def test_min_trl_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="exceed"):
        minimum_track_record_length(0.1, 0.1)
    with pytest.raises(ValueError, match="confidence"):
        minimum_track_record_length(0.1, 0.0, confidence=1.0)
