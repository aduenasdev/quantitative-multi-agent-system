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
    """Equal weights on the top (and bottom) ``quantile`` of the finite scores of each row."""
    valid = np.isfinite(scores)
    n_valid = valid.sum(axis=1)
    minimum = 2 if strategy.portfolio == "long_short" else 1
    count = np.maximum(1, np.floor(n_valid * strategy.quantile).astype(int))
    filled = np.where(valid, scores, np.inf)
    order = np.argsort(filled, axis=1, kind="stable")
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(scores.shape[1])[None, :], axis=1)
    enough = (n_valid >= minimum)[:, None]
    weight = (1.0 / count)[:, None]
    weights = np.where(enough & valid & (rank >= (n_valid - count)[:, None]), weight, 0.0)
    if strategy.portfolio == "long_short":
        weights = np.where(enough & valid & (rank < count[:, None]), -weight, weights)
    result: np.ndarray = weights
    return result


def _holdings(
    weights: np.ndarray, entries: np.ndarray, n_days: int, strategy: StrategySpec
) -> np.ndarray:
    """Return daily holdings: the sum of the tranches alive on each day (at most ``tranches``)."""
    held = np.zeros((n_days, weights.shape[1]))
    if entries.size == 0:
        return held
    days = np.arange(n_days)
    latest = np.searchsorted(entries, days, side="right") - 1
    share = 1.0 / strategy.tranches
    for back in range(strategy.tranches):
        index = latest - back
        active = (index >= 0) & (days < entries[np.maximum(index, 0)] + strategy.horizon_days)
        held[active] += weights[index[active]] * share
    return held


def run_backtest(
    market: SyntheticMarket, strategy: StrategySpec, signal: np.ndarray | None = None
) -> BacktestResult:
    """Run ``strategy`` on ``market`` and return daily gross and net returns over its window.

    ``signal`` replaces the registered signal with a precomputed matrix (used by the placebo).
    """
    first, last = _window_indices(market, strategy)
    if signal is None:
        signal = compute_signal(strategy.signal, market, strategy.signal_parameters)
    elif signal.shape != market.returns.shape:
        raise ValueError("signal must have the shape of the market returns")
    tradable = _tradable(market, strategy)
    source = market.secondary_returns if strategy.price_source == "secondary" else market.returns
    returns = np.nan_to_num(source, nan=0.0)
    unit_costs = (
        market.cost_bps
        if strategy.cost_model == "per_name"
        else np.full(market.n_assets, strategy.cost_bps)
    ) / BASIS_POINTS

    # Decide with the information of the close of each rebalancing day; trade
    # ``execution_delay`` days later and hold for ``horizon_days``.
    days = np.arange(first + strategy.offset, last - 1, strategy.rebalance_every_days)
    entries = days + 1 + strategy.execution_delay
    days, entries = days[entries < last], entries[entries < last]
    weights = _weights(np.where(tradable[days], signal[days], np.nan), strategy)
    previous = np.zeros_like(weights)
    previous[strategy.tranches :] = weights[: -strategy.tranches or None]
    change = np.abs(weights - previous) / strategy.tranches
    turnover = np.zeros(market.n_days)
    costs = np.zeros(market.n_days)
    np.add.at(turnover, entries, change.sum(axis=1))
    np.add.at(costs, entries, change @ unit_costs)
    held = _holdings(weights, entries, last, strategy)
    names = np.count_nonzero(weights, axis=1)

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
        n_rebalances=int(names.size),
        average_names=float(np.mean(names)) if names.size else 0.0,
    )
