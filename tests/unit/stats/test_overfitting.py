from __future__ import annotations

import numpy as np
import pytest

from qmas.stats.overfitting import probability_of_backtest_overfitting


def test_pbo_of_pure_noise_is_about_one_half() -> None:
    rng = np.random.default_rng(3)
    estimates = [
        probability_of_backtest_overfitting(rng.normal(0, 0.01, (800, 40)), n_blocks=10).probability
        for _ in range(8)
    ]
    assert float(np.mean(estimates)) == pytest.approx(0.5, abs=0.12)


def test_pbo_with_a_dominant_trial_is_close_to_zero() -> None:
    rng = np.random.default_rng(4)
    performance = rng.normal(0, 0.01, (1000, 30))
    performance[:, 7] += 0.004
    result = probability_of_backtest_overfitting(performance, n_blocks=10)
    assert result.probability < 0.05
    assert result.n_splits == 252
    assert result.logits.shape == (252,)


def test_pbo_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="two trials"):
        probability_of_backtest_overfitting(np.zeros((100, 1)))
    with pytest.raises(ValueError, match="even"):
        probability_of_backtest_overfitting(np.zeros((100, 3)), n_blocks=5)
    with pytest.raises(ValueError, match="two periods"):
        probability_of_backtest_overfitting(np.zeros((10, 3)), n_blocks=8)
    with pytest.raises(ValueError, match="finite"):
        probability_of_backtest_overfitting(np.full((100, 3), np.nan), n_blocks=4)
