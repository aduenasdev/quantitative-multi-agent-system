"""Probability of backtest overfitting through combinatorially symmetric cross-validation (CSCV).

Reference:
    Bailey, D. H., Borwein, J., López de Prado, M. and Zhu, Q. J. (2017). "The Probability of
        Backtest Overfitting." Journal of Computational Finance 20(4).

The rows of the performance matrix are time, the columns are the trials (configurations) a
researcher chose from. The rows are cut into ``n_blocks`` contiguous blocks; every half of the
blocks is used once as in-sample and its complement as out-of-sample. For each split the best
in-sample trial is located in the out-of-sample ranking. PBO is the share of splits in which
that trial ranks at or below the median.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats


@dataclass(frozen=True)
class OverfittingResult:
    """Outcome of CSCV."""

    probability: float
    logits: np.ndarray
    n_splits: int


def _block_sharpe(sums: np.ndarray, squares: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Sharpe ratio per row of aggregated block sums (rows: splits, columns: trials)."""
    n = counts[:, None]
    mean = sums / n
    variance = (squares - n * mean**2) / (n - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        result: np.ndarray = np.where(variance > 0, mean / np.sqrt(variance), 0.0)
    return result


def probability_of_backtest_overfitting(
    performance: ArrayLike, n_blocks: int = 16
) -> OverfittingResult:
    """Return the probability that the in-sample winner is below median out of sample.

    Args:
        performance: matrix of per-period returns, shape (n_periods, n_trials).
        n_blocks: even number of contiguous row blocks (16 gives 12,870 splits).
    """
    matrix = np.asarray(performance, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        raise ValueError("performance must be a 2-D matrix with at least two trials")
    if n_blocks < 2 or n_blocks % 2:
        raise ValueError("n_blocks must be an even number of at least 2")
    if matrix.shape[0] < 2 * n_blocks:
        raise ValueError("need at least two periods per block")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("performance must be finite")

    blocks = np.array_split(np.arange(matrix.shape[0]), n_blocks)
    block_sums = np.array([matrix[rows].sum(axis=0) for rows in blocks])
    block_squares = np.array([(matrix[rows] ** 2).sum(axis=0) for rows in blocks])
    block_counts = np.array([rows.size for rows in blocks], dtype=float)

    selection_list = [
        np.isin(np.arange(n_blocks), chosen).astype(float)
        for chosen in combinations(range(n_blocks), n_blocks // 2)
    ]
    selections = np.array(selection_list)
    complements = 1.0 - selections

    in_sample = _block_sharpe(
        selections @ block_sums, selections @ block_squares, selections @ block_counts
    )
    out_of_sample = _block_sharpe(
        complements @ block_sums, complements @ block_squares, complements @ block_counts
    )
    best = np.argmax(in_sample, axis=1)
    ranks = stats.rankdata(out_of_sample, axis=1)
    n_trials = matrix.shape[1]
    relative_rank = ranks[np.arange(best.size), best] / (n_trials + 1)
    logits = np.log(relative_rank / (1.0 - relative_rank))
    return OverfittingResult(
        probability=float(np.mean(logits <= 0)), logits=logits, n_splits=int(best.size)
    )
