"""Purged k-fold cross-validation with an embargo.

Reference:
    López de Prado, M. (2018). Advances in Financial Machine Learning. Wiley. Chapter 7.

Observation ``i`` has a label that depends on periods ``i .. i + label_horizon``. A training
observation is purged when its label window overlaps the label windows of the test fold, and
embargoed when it starts within ``embargo`` periods after the end of those windows, so that
serial correlation cannot leak information from test to train.
"""

from __future__ import annotations

import numpy as np

Fold = tuple[np.ndarray, np.ndarray]


def purged_k_fold(
    n_samples: int, n_splits: int, label_horizon: int = 0, embargo: int = 0
) -> list[Fold]:
    """Return ``(train_indices, test_indices)`` for each of ``n_splits`` contiguous test folds."""
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    if n_samples < n_splits:
        raise ValueError("n_samples must be at least n_splits")
    if label_horizon < 0 or embargo < 0:
        raise ValueError("label_horizon and embargo must be non-negative")
    indices = np.arange(n_samples)
    folds: list[Fold] = []
    for test in np.array_split(indices, n_splits):
        first_test, last_test = int(test[0]), int(test[-1])
        overlaps_test = (indices + label_horizon >= first_test) & (
            indices <= last_test + label_horizon + embargo
        )
        folds.append((indices[~overlaps_test], test))
    return folds
