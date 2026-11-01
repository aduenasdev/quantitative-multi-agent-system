"""Registry of signals a thesis can name.

A signal maps a market and its parameters to a matrix of shape (n_days, n_assets) whose row ``t``
is what the signal claims to know at the close of day ``t``; NaN means "no view". Theses choose
signals by name; no code is ever read from a thesis file.

Two signals are defective on purpose, to plant defects for the red-team evaluation:

* ``future_return`` uses the next day's return (look-ahead, defect P1);
* ``event_surprise`` with ``timestamps_as_utc=True`` treats New York clock times as UTC, which makes
  after-close events look known before the close (defect P6).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from qmas.market.generator import MINUTES_MARKET_CLOSE, TRADING_DAYS_PER_YEAR, SyntheticMarket

ParameterValue = int | float | str | bool
Parameters = Mapping[str, ParameterValue]
SignalFunction = Callable[[SyntheticMarket, Parameters], np.ndarray]

NEW_YORK_UTC_OFFSET_MINUTES = 5 * 60


def _int(parameters: Parameters, name: str, default: int) -> int:
    value = parameters.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"signal parameter {name!r} must be an integer")
    return value


def _bool(parameters: Parameters, name: str, default: bool) -> bool:
    value = parameters.get(name, default)
    if not isinstance(value, bool):
        raise TypeError(f"signal parameter {name!r} must be a boolean")
    return value


def _mask_dead(market: SyntheticMarket, values: np.ndarray) -> np.ndarray:
    result: np.ndarray = np.where(market.alive, values, np.nan)
    return result


def planted_characteristic(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return the planted characteristic, known from the start of its block."""
    return _mask_dead(market, market.characteristic)


def future_return(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return the next day's return as if it were known today (defect P1: look-ahead)."""
    values = np.full_like(market.returns, np.nan)
    values[:-1] = market.returns[1:]
    return _mask_dead(market, values)


def short_term_reversal(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return minus today's return: yesterday's losers are expected to bounce."""
    return _mask_dead(market, -market.returns)


def trailing_return(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return the trailing ``days`` return; ``invert=True`` ranks losers first."""
    days = _int(parameters, "days", TRADING_DAYS_PER_YEAR)
    if days < 1:
        raise ValueError("days must be positive")
    log_wealth = np.cumsum(np.log1p(np.nan_to_num(market.returns, nan=0.0)), axis=0)
    values = np.full_like(market.returns, np.nan)
    values[days:] = np.expm1(log_wealth[days:] - log_wealth[:-days])
    if _bool(parameters, "invert", False):
        values = -values
    return _mask_dead(market, values)


def random_characteristic(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return pure noise, constant within each block (a candidate with no predictive power)."""
    rng = np.random.default_rng([market.seed, _int(parameters, "seed", 0)])
    draws = rng.standard_normal((market.block_starts.size, market.n_assets))
    return _mask_dead(market, draws[market.block_of_day()])


def beta_exposure(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return each stock's market beta (a disguised market bet, defect P10)."""
    values = np.broadcast_to(market.betas, market.returns.shape).astype(float)
    return _mask_dead(market, values)


def event_surprise(market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Return the surprise of each event on the day it is known at the close.

    An event is known at the close of its day if it happened before 16:00 New York time, otherwise
    at the next close. ``timestamps_as_utc=True`` reproduces a time-zone bug (defect P6): the New
    York clock time is read as UTC and converted, so it looks five hours earlier.
    """
    events = market.events
    minutes = events["minutes"].copy()
    if _bool(parameters, "timestamps_as_utc", False):
        minutes -= NEW_YORK_UTC_OFFSET_MINUTES
    known_day = events["day"] + (minutes >= MINUTES_MARKET_CLOSE)
    inside = known_day < market.n_days
    values = np.full_like(market.returns, np.nan)
    values[known_day[inside], events["asset"][inside]] = events["surprise"][inside]
    return _mask_dead(market, values)


SIGNALS: dict[str, SignalFunction] = {
    "planted_characteristic": planted_characteristic,
    "future_return": future_return,
    "short_term_reversal": short_term_reversal,
    "trailing_return": trailing_return,
    "random_characteristic": random_characteristic,
    "beta_exposure": beta_exposure,
    "event_surprise": event_surprise,
}


def compute_signal(name: str, market: SyntheticMarket, parameters: Parameters) -> np.ndarray:
    """Evaluate the registered signal ``name``; unknown names raise ``KeyError``."""
    try:
        function = SIGNALS[name]
    except KeyError:
        known = ", ".join(sorted(SIGNALS))
        raise KeyError(f"unknown signal {name!r}; known signals: {known}") from None
    return function(market, parameters)
