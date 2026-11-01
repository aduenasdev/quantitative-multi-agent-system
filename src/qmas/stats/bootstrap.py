"""Block bootstrap for dependent observations.

Overlapping holding periods make neighbouring observations dependent, so resampling single
observations understates the variance. Two schemes are provided:

* moving-block bootstrap of a time series (Künsch, 1989): contiguous blocks of ``block_length``;
* grouped bootstrap of events: whole calendar blocks (groups) are resampled with replacement,
  the same groups for every sample being compared.

Reference:
    Künsch, H. R. (1989). "The Jackknife and the Bootstrap for General Stationary Observations."
        Annals of Statistics 17(3).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike

Statistic = Callable[[np.ndarray], float]
PairedStatistic = Callable[[np.ndarray, np.ndarray], float]


def moving_block_indices(n: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    """Return the indices of one moving-block resample of a series of length ``n``."""
    if n < 1:
        raise ValueError("n must be positive")
    if not 1 <= block_length <= n:
        raise ValueError("block_length must be between 1 and n")
    n_blocks = -(-n // block_length)
    starts = rng.integers(0, n - block_length + 1, size=n_blocks)
    indices = (starts[:, None] + np.arange(block_length)[None, :]).ravel()
    return indices[:n]


def block_bootstrap(
    values: ArrayLike,
    statistic: Statistic,
    block_length: int,
    n_resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return replicates of ``statistic`` over moving-block resamples of a series."""
    series = np.asarray(values, dtype=float)
    return np.array(
        [
            statistic(series[moving_block_indices(series.size, block_length, rng)])
            for _ in range(n_resamples)
        ]
    )


def paired_block_bootstrap(
    first: ArrayLike,
    second: ArrayLike,
    statistic: PairedStatistic,
    block_length: int,
    n_resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return replicates of ``statistic(first*, second*)`` using the same blocks for both series."""
    a = np.asarray(first, dtype=float)
    b = np.asarray(second, dtype=float)
    if a.shape != b.shape:
        raise ValueError("series must be aligned")
    replicates = []
    for _ in range(n_resamples):
        indices = moving_block_indices(a.size, block_length, rng)
        replicates.append(statistic(a[indices], b[indices]))
    return np.array(replicates)


def _split_by_group(
    values: np.ndarray, groups: np.ndarray, universe: np.ndarray
) -> list[np.ndarray]:
    order = np.argsort(groups, kind="stable")
    sorted_values, sorted_groups = values[order], groups[order]
    starts = np.searchsorted(sorted_groups, universe, side="left")
    ends = np.searchsorted(sorted_groups, universe, side="right")
    return [sorted_values[i:j] for i, j in zip(starts, ends, strict=True)]


def grouped_bootstrap(
    values: ArrayLike,
    groups: ArrayLike,
    statistic: Statistic,
    n_resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return replicates of ``statistic`` resampling whole groups (such as calendar blocks)."""
    data = np.asarray(values, dtype=float)
    labels = np.asarray(groups)
    universe = np.unique(labels)
    pieces = _split_by_group(data, labels, universe)
    replicates = np.empty(n_resamples)
    for k in range(n_resamples):
        chosen = rng.integers(0, universe.size, universe.size)
        sample = np.concatenate([pieces[i] for i in chosen])
        replicates[k] = statistic(sample) if sample.size else np.nan
    return replicates


def grouped_bootstrap_two_samples(
    first: ArrayLike,
    first_groups: ArrayLike,
    second: ArrayLike,
    second_groups: ArrayLike,
    statistic: PairedStatistic,
    n_resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return replicates of ``statistic(first*, second*)`` drawing the same groups for both."""
    a, b = np.asarray(first, dtype=float), np.asarray(second, dtype=float)
    labels_a, labels_b = np.asarray(first_groups), np.asarray(second_groups)
    universe = np.union1d(np.unique(labels_a), np.unique(labels_b))
    pieces_a = _split_by_group(a, labels_a, universe)
    pieces_b = _split_by_group(b, labels_b, universe)
    replicates = np.empty(n_resamples)
    for k in range(n_resamples):
        chosen = rng.integers(0, universe.size, universe.size)
        sample_a = np.concatenate([pieces_a[i] for i in chosen])
        sample_b = np.concatenate([pieces_b[i] for i in chosen])
        replicates[k] = statistic(sample_a, sample_b) if sample_a.size and sample_b.size else np.nan
    return replicates


def one_sided_p_value(replicates: ArrayLike, null_value: float) -> float:
    """Return the add-one smoothed share of replicates at or below ``null_value``.

    The alternative hypothesis is that the statistic exceeds ``null_value``.
    """
    values = np.asarray(replicates, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("no finite replicates")
    return float((np.sum(values <= null_value) + 1) / (values.size + 1))


def percentile_interval(replicates: ArrayLike, confidence: float = 0.95) -> tuple[float, float]:
    """Return the two-sided percentile confidence interval of the replicates."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    values = np.asarray(replicates, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("no finite replicates")
    tail = (1.0 - confidence) / 2.0 * 100.0
    low, high = np.percentile(values, [tail, 100.0 - tail])
    return float(low), float(high)
