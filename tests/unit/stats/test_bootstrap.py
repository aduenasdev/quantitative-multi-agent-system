from __future__ import annotations

import numpy as np
import pytest

from qmas.stats.bootstrap import (
    block_bootstrap,
    grouped_bootstrap,
    grouped_bootstrap_two_samples,
    moving_block_indices,
    one_sided_p_value,
    paired_block_bootstrap,
    percentile_interval,
)


def _mean(values: np.ndarray) -> float:
    return float(np.mean(values))


def _difference(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.mean(first) - np.mean(second))


def test_moving_block_indices_are_contiguous_blocks() -> None:
    indices = moving_block_indices(23, 5, np.random.default_rng(0))
    assert indices.shape == (23,)
    assert indices.min() >= 0
    assert indices.max() < 23
    for start in range(0, 20, 5):
        assert np.all(np.diff(indices[start : start + 5]) == 1)


def test_moving_block_indices_reject_bad_lengths() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="positive"):
        moving_block_indices(0, 1, rng)
    with pytest.raises(ValueError, match="block_length"):
        moving_block_indices(5, 6, rng)


def test_block_bootstrap_is_reproducible_and_centred() -> None:
    series = np.random.default_rng(1).normal(0.5, 1.0, 500)
    first = block_bootstrap(series, _mean, 20, 300, np.random.default_rng(9))
    second = block_bootstrap(series, _mean, 20, 300, np.random.default_rng(9))
    np.testing.assert_array_equal(first, second)
    assert float(first.mean()) == pytest.approx(series.mean(), abs=0.02)


def test_block_bootstrap_widens_intervals_for_dependent_data() -> None:
    rng = np.random.default_rng(2)
    shocks = rng.normal(0, 1, 2000)
    dependent = np.convolve(shocks, np.ones(20) / 20, mode="valid")
    narrow = block_bootstrap(dependent, _mean, 1, 400, np.random.default_rng(3))
    wide = block_bootstrap(dependent, _mean, 50, 400, np.random.default_rng(3))
    assert wide.std() > 2 * narrow.std()


def test_paired_block_bootstrap_uses_the_same_blocks() -> None:
    series = np.random.default_rng(4).normal(0, 1, 300)
    replicates = paired_block_bootstrap(
        series, series, _difference, 10, 50, np.random.default_rng(5)
    )
    np.testing.assert_allclose(replicates, 0.0)
    with pytest.raises(ValueError, match="aligned"):
        paired_block_bootstrap(series, series[:-1], _difference, 10, 5, np.random.default_rng(5))


def test_grouped_bootstrap_resamples_whole_groups() -> None:
    values = np.array([1.0, 1.0, 10.0, 10.0])
    groups = np.array([0, 0, 1, 1])
    replicates = grouped_bootstrap(values, groups, _mean, 200, np.random.default_rng(6))
    assert set(np.round(replicates, 6)) <= {1.0, 5.5, 10.0}


def test_grouped_bootstrap_two_samples_draws_shared_groups() -> None:
    values = np.array([1.0, 2.0, 3.0])
    groups = np.array([0, 1, 2])
    replicates = grouped_bootstrap_two_samples(
        values, groups, values, groups, _difference, 100, np.random.default_rng(7)
    )
    np.testing.assert_allclose(replicates, 0.0)


def test_grouped_bootstrap_two_samples_with_disjoint_groups_gives_nan() -> None:
    replicates = grouped_bootstrap_two_samples(
        np.array([1.0]),
        np.array([0]),
        np.array([2.0]),
        np.array([1]),
        _difference,
        200,
        np.random.default_rng(8),
    )
    assert np.isnan(replicates).any()
    assert np.isfinite(replicates).any()


def test_one_sided_p_value_and_interval() -> None:
    replicates = np.arange(1.0, 100.0)
    assert one_sided_p_value(replicates, 0.0) == pytest.approx(1 / 100)
    assert one_sided_p_value(np.append(replicates, np.nan), 99.0) == pytest.approx(1.0)
    low, high = percentile_interval(replicates, 0.9)
    assert low == pytest.approx(np.percentile(replicates, 5))
    assert high == pytest.approx(np.percentile(replicates, 95))


def test_p_value_and_interval_reject_empty_input() -> None:
    with pytest.raises(ValueError, match="finite"):
        one_sided_p_value([np.nan], 0.0)
    with pytest.raises(ValueError, match="finite"):
        percentile_interval([np.nan])
    with pytest.raises(ValueError, match="confidence"):
        percentile_interval([1.0], 1.5)
