from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from qmas.stats.cross_validation import purged_k_fold


@given(
    n_samples=st.integers(20, 300),
    n_splits=st.integers(2, 8),
    horizon=st.integers(0, 10),
    embargo=st.integers(0, 10),
)
def test_no_training_label_overlaps_a_test_label(
    n_samples: int, n_splits: int, horizon: int, embargo: int
) -> None:
    folds = purged_k_fold(n_samples, n_splits, horizon, embargo)
    tested = np.concatenate([test for _, test in folds])
    np.testing.assert_array_equal(tested, np.arange(n_samples))
    for train, test in folds:
        first, last = test[0], test[-1]
        assert np.all((train + horizon < first) | (train > last + horizon + embargo))
        assert np.intersect1d(train, test).size == 0


def test_without_horizon_or_embargo_train_is_the_complement() -> None:
    train, test = purged_k_fold(10, 2)[0]
    np.testing.assert_array_equal(test, np.arange(5))
    np.testing.assert_array_equal(train, np.arange(5, 10))


def test_purged_k_fold_validation() -> None:
    with pytest.raises(ValueError, match="n_splits"):
        purged_k_fold(10, 1)
    with pytest.raises(ValueError, match="n_samples"):
        purged_k_fold(2, 3)
    with pytest.raises(ValueError, match="non-negative"):
        purged_k_fold(10, 2, label_horizon=-1)
