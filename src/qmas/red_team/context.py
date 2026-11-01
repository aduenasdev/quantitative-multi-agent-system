"""Inputs shared by every attack, and the pre-registered thresholds."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from qmas.backtest import BacktestResult, StrategySpec, run_backtest
from qmas.market import SyntheticMarket


@dataclass(frozen=True)
class BatteryThresholds:
    """Every threshold of the battery, fixed before the E1 evaluation.

    Calibrated on calibration seeds 1000-1004 only; judgement seeds never tune them.
    """

    delay_min_retention: float = 0.5
    survivorship_max_gap: float = 0.3
    survivorship_max_relative_gap: float = 0.5
    cost_min_retention: float = 0.3
    min_deflated_sharpe: float = 0.95
    max_overfitting_probability: float = 0.5
    placebo_runs: int = 200
    max_p_value: float = 0.05
    min_probabilistic_sharpe: float = 0.95
    power: float = 0.80
    factor_min_t_statistic: float = 1.645
    factor_min_retention: float = 0.5
    regime_subperiods: int = 3
    regime_max_share: float = 0.6
    calendar_min_retention: float = 0.25
    concentration_max_share: float = 0.5
    concentration_min_retention: float = 0.5
    source_max_gap: float = 0.1
    source_max_relative_gap: float = 0.2
    suspicious_sharpe: float = 2.0

    def with_overrides(self, **changes: Any) -> BatteryThresholds:
        """Return a copy with some thresholds changed (for quick runs and tests)."""
        return replace(self, **changes)


@dataclass(frozen=True)
class TrialSet:
    """Every trial of the thesis family: their count and, when available, their daily returns."""

    n_trials: int = 1
    returns: np.ndarray | None = None

    def __post_init__(self) -> None:
        """Validate the trial set."""
        if self.n_trials < 1:
            raise ValueError("n_trials must be at least 1")
        if self.returns is not None and self.returns.ndim != 2:
            raise ValueError("trial returns must be a (days, trials) matrix")


@dataclass
class AttackContext:
    """The claim under attack and everything needed to re-run it."""

    market: SyntheticMarket
    strategy: StrategySpec
    trials: TrialSet
    thresholds: BatteryThresholds
    seed: int
    claimed: BacktestResult | None = None

    def __post_init__(self) -> None:
        """Run the claimed backtest once, unless it was given."""
        if self.claimed is None:
            self.claimed = run_backtest(self.market, self.strategy)

    @property
    def claim(self) -> BacktestResult:
        """Return the claimed backtest."""
        if self.claimed is None:  # pragma: no cover - set in __post_init__
            raise RuntimeError("claimed backtest missing")
        return self.claimed

    @property
    def claimed_sharpe(self) -> float:
        """Return the annualised net Sharpe ratio of the claim."""
        return self.claim.sharpe()

    def rerun(self, **changes: Any) -> BacktestResult:
        """Re-run the claimed strategy with some switches flipped."""
        return run_backtest(self.market, replace(self.strategy, **changes))
