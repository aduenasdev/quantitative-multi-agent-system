"""Overlapping-portfolio backtest of a ranked signal.

Reference:
    Jegadeesh, N. and Titman, S. (1993). "Returns to Buying Winners and Selling Losers:
        Implications for Stock Market Efficiency." Journal of Finance 48(1). Overlapping
        holding-period portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qmas.backtest.strategy import StrategySpec
from qmas.market import SyntheticMarket
from qmas.market.generator import TRADING_DAYS_PER_YEAR
from qmas.market.signals import compute_signal

BASIS_POINTS = 1e4


@dataclass(frozen=True)
class BacktestResult:
    """Daily results of a strategy over its window."""

    strategy: StrategySpec
    dates: np.ndarray
    gross_returns: np.ndarray
    net_returns: np.ndarray
    turnover: np.ndarray
    contributions: np.ndarray
    n_rebalances: int
    average_names: float

    def returns(self, net: bool = True) -> np.ndarray:
        """Return the daily net (default) or gross returns."""
        return self.net_returns if net else self.gross_returns

    def sharpe(self, net: bool = True) -> float:
        """Return the annualised Sharpe ratio; 0 when the returns have no variance."""
        values = self.returns(net)
        deviation = float(np.std(values, ddof=1))
        if deviation == 0.0:
            return 0.0
        return float(np.mean(values) / deviation * np.sqrt(TRADING_DAYS_PER_YEAR))


def _window_indices(market: SyntheticMarket, strategy: StrategySpec) -> tuple[int, int]:
    first = int(np.searchsorted(market.dates, np.datetime64(strategy.start, "D"), side="left"))
    last = int(np.searchsorted(market.dates, np.datetime64(strategy.end, "D"), side="right"))
    if last - first < 2:
        raise ValueError("the strategy window does not overlap the market dates")
    return first, last


def _tradable(market: SyntheticMarket, strategy: StrategySpec) -> np.ndarray:
    tradable = market.alive.copy()
    if strategy.universe == "survivors":
        tradable &= market.survivors()[None, :]
    if strategy.excluded_assets:
        tradable[:, sorted(strategy.excluded_assets)] = False
    return tradable


def _weights(scores: np.ndarray, strategy: StrategySpec) -> np.ndarray:
    """Equal weights on the top (and bottom) ``quantile`` of the finite scores."""
    weights = np.zeros(scores.size)
    valid = np.flatnonzero(np.isfinite(scores))
    minimum = 2 if strategy.portfolio == "long_short" else 1
    if valid.size < minimum:
        return weights
    count = max(1, int(np.floor(valid.size * strategy.quantile)))
    order = valid[np.argsort(scores[valid], kind="stable")]
    weights[order[-count:]] = 1.0 / count
    if strategy.portfolio == "long_short":
        weights[order[:count]] = -1.0 / count
    return weights


def run_backtest(market: SyntheticMarket, strategy: StrategySpec) -> BacktestResult:
    """Run ``strategy`` on ``market`` and return daily gross and net returns over its window."""
    first, last = _window_indices(market, strategy)
    signal = compute_signal(strategy.signal, market, strategy.signal_parameters)
    tradable = _tradable(market, strategy)
    source = market.secondary_returns if strategy.price_source == "secondary" else market.returns
    returns = np.nan_to_num(source, nan=0.0)
    unit_costs = (
        market.cost_bps
        if strategy.cost_model == "per_name"
        else np.full(market.n_assets, strategy.cost_bps)
    ) / BASIS_POINTS

    n_days, n_assets = market.n_days, market.n_assets
    held = np.zeros((n_days + 1, n_assets))
    turnover = np.zeros(n_days + 1)
    costs = np.zeros(n_days + 1)
    previous = np.zeros((strategy.tranches, n_assets))
    share = 1.0 / strategy.tranches
    rebalance_days = range(first + strategy.offset, last - 1, strategy.rebalance_every_days)
    names = []
    for number, day in enumerate(rebalance_days):
        # Decide with the information of the close of ``day``; trade ``execution_delay`` days later.
        entry = day + 1 + strategy.execution_delay
        if entry >= last:
            break
        weights = _weights(np.where(tradable[day], signal[day], np.nan), strategy)
        slot = number % strategy.tranches
        change = np.abs(weights - previous[slot]) * share
        previous[slot] = weights
        turnover[entry] += float(change.sum())
        costs[entry] += float(change @ unit_costs)
        held[entry : min(entry + strategy.horizon_days, last)] += weights * share
        names.append(int(np.count_nonzero(weights)))

    window = slice(first, last)
    position_returns = held[window] * returns[window]
    gross = position_returns.sum(axis=1)
    net = gross - costs[window]
    return BacktestResult(
        strategy=strategy,
        dates=market.dates[window],
        gross_returns=gross,
        net_returns=net,
        turnover=turnover[window],
        contributions=position_returns.sum(axis=0),
        n_rebalances=len(names),
        average_names=float(np.mean(names)) if names else 0.0,
    )
