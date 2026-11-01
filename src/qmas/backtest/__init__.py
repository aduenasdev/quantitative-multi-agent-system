"""Deterministic cross-sectional backtest engine."""

from qmas.backtest.engine import BacktestResult, run_backtest
from qmas.backtest.strategy import StrategySpec, market_from_thesis, strategy_from_thesis

__all__ = [
    "BacktestResult",
    "StrategySpec",
    "market_from_thesis",
    "run_backtest",
    "strategy_from_thesis",
]
