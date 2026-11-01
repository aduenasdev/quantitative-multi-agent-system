"""Synthetic daily equity market.

Returns follow a factor model with fat tails and volatility clustering:

    r[t, i] = beta[i] * f[t] + s[t, sector(i)] + v[t] * sigma[i] * e[t, i]
              + planted drift + event reactions + jump

* ``f`` is a GARCH(1, 1) market factor with Student-t innovations; ``v`` is its volatility
  relative to the long-run level, shared by every stock (volatility clustering);
* ``s`` are sector factors, ``e`` Student-t idiosyncratic shocks (an MA(1) with negative
  coefficient when ``reversal_strength`` is positive);
* the planted characteristic is redrawn at every block start and shifts the expected return of the
  block so that its cross-sectional correlation with the block return equals ``planted_ic``.

Delistings happen with a hazard that grows with the trailing one-year loss, end with
``delisting_return`` and leave NaN afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

TRADING_DAYS_PER_YEAR = 252
MINUTES_MARKET_OPEN = 9 * 60 + 30
MINUTES_MARKET_CLOSE = 16 * 60

EVENT_DTYPE = np.dtype(
    [
        ("asset", np.int64),
        ("day", np.int64),
        ("minutes", np.int64),
        ("surprise", np.float64),
        ("reaction_day", np.int64),
    ]
)


@dataclass(frozen=True)
class MarketConfig:
    """Parameters of the synthetic market. Defaults give a realistic, defect-free market."""

    n_assets: int = 200
    start: date = date(2016, 1, 4)
    end: date = date(2023, 12, 29)
    n_sectors: int = 8
    market_drift_annual: float = 0.06
    market_vol_annual: float = 0.16
    garch_alpha: float = 0.06
    garch_beta: float = 0.92
    tail_degrees_of_freedom: float = 5.0
    beta_mean: float = 1.0
    beta_std: float = 0.3
    sector_vol_annual: float = 0.08
    idio_vol_annual_range: tuple[float, float] = (0.15, 0.45)
    base_cost_bps: float = 10.0
    # Planted characteristic.
    planted_ic: float = 0.0
    signal_horizon: int = 21
    signal_active_years: tuple[int, ...] | None = None
    signal_front_loaded: bool = False
    # Short-term reversal (MA(1) coefficient of the idiosyncratic shocks).
    reversal_strength: float = 0.0
    # Delistings.
    delisting_rate_annual: float = 0.01
    delisting_loser_sensitivity: float = 4.0
    delisting_return: float = -0.30
    # Log decline spread over the days before a delisting (the slide towards it), 0 for none.
    distress_decline: float = 0.0
    distress_days: int = 126
    # Events with New York clock times.
    events_per_year: float = 4.0
    event_reaction_vol: float = 2.0
    # Single-name jump (in the primary and secondary sources) and data error (primary only).
    jump_size: float = 0.0
    price_error_size: float = 0.0
    defect_year: int = 2019

    def __post_init__(self) -> None:
        """Validate the parameters."""
        if self.n_assets < 10:
            raise ValueError("n_assets must be at least 10")
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if not -1.0 < self.planted_ic < 1.0:
            raise ValueError("planted_ic must be in (-1, 1)")
        if self.signal_horizon < 1:
            raise ValueError("signal_horizon must be positive")
        if self.garch_alpha + self.garch_beta >= 1.0:
            raise ValueError("GARCH parameters must satisfy alpha + beta < 1")
        if self.tail_degrees_of_freedom <= 2.0:
            raise ValueError("tail_degrees_of_freedom must exceed 2")


@dataclass(frozen=True)
class SyntheticMarket:
    """A generated market. Arrays are read-only by convention."""

    config: MarketConfig
    seed: int
    dates: np.ndarray
    asset_ids: tuple[str, ...]
    returns: np.ndarray
    secondary_returns: np.ndarray
    alive: np.ndarray
    delisting_day: np.ndarray
    market_factor: np.ndarray
    betas: np.ndarray
    sectors: np.ndarray
    idio_vol: np.ndarray
    cost_bps: np.ndarray
    characteristic: np.ndarray
    block_starts: np.ndarray
    events: np.ndarray
    defects: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def n_days(self) -> int:
        """Return the number of trading days."""
        return int(self.dates.size)

    @property
    def n_assets(self) -> int:
        """Return the number of assets."""
        return int(self.betas.size)

    def survivors(self) -> np.ndarray:
        """Return a mask of the assets that are still listed on the last day."""
        mask: np.ndarray = self.delisting_day < 0
        return mask

    def block_of_day(self) -> np.ndarray:
        """Return, for each day, the index of the block that contains it."""
        index: np.ndarray = (
            np.searchsorted(self.block_starts, np.arange(self.n_days), side="right") - 1
        )
        return index


def business_days(start: date, end: date) -> np.ndarray:
    """Return the weekdays from ``start`` to ``end`` inclusive (no holiday calendar)."""
    first = np.datetime64(start, "D")
    after_last = np.datetime64(end, "D") + np.timedelta64(1, "D")
    days = np.arange(first, after_last, dtype="datetime64[D]")
    result: np.ndarray = days[np.is_busday(days)]
    return result


def standard_t(rng: np.random.Generator, df: float, size: tuple[int, ...] | int) -> np.ndarray:
    """Student-t draws rescaled to unit variance."""
    draws: np.ndarray = rng.standard_t(df, size) * np.sqrt((df - 2.0) / df)
    return draws


def _market_factor(
    config: MarketConfig, n_days: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """GARCH(1, 1) market returns and their volatility relative to the long-run level."""
    long_run_variance = (config.market_vol_annual**2) / TRADING_DAYS_PER_YEAR
    omega = long_run_variance * (1.0 - config.garch_alpha - config.garch_beta)
    shocks = standard_t(rng, config.tail_degrees_of_freedom, n_days)
    variance = np.empty(n_days)
    returns = np.empty(n_days)
    variance[0] = long_run_variance
    drift = config.market_drift_annual / TRADING_DAYS_PER_YEAR
    for t in range(n_days):
        if t > 0:
            innovation = returns[t - 1] - drift
            variance[t] = (
                omega + config.garch_alpha * innovation**2 + config.garch_beta * variance[t - 1]
            )
        returns[t] = drift + np.sqrt(variance[t]) * shocks[t]
    return returns, np.sqrt(variance / long_run_variance)


def _idiosyncratic(
    config: MarketConfig,
    n_days: int,
    idio_vol: np.ndarray,
    relative_vol: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    shocks = standard_t(rng, config.tail_degrees_of_freedom, (n_days, config.n_assets))
    if config.reversal_strength:
        shocks[1:] -= config.reversal_strength * shocks[:-1]
    result: np.ndarray = shocks * idio_vol[None, :] * relative_vol[:, None]
    return result


def _plant_characteristic(
    config: MarketConfig,
    returns: np.ndarray,
    dates: np.ndarray,
    block_starts: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw the block characteristic and return it with the drift that plants ``planted_ic``."""
    n_days, n_assets = returns.shape
    horizon = config.signal_horizon
    characteristic = np.empty((n_days, n_assets))
    drift = np.zeros((n_days, n_assets))
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    ic = config.planted_ic
    for start in block_starts:
        stop = min(start + horizon, n_days - 1)
        z = rng.standard_normal(n_assets)
        characteristic[start : start + horizon] = z
        if ic == 0.0 or stop <= start:
            continue
        if (
            config.signal_active_years is not None
            and int(years[start]) not in config.signal_active_years
        ):
            continue
        forward = returns[start + 1 : stop + 1].sum(axis=0)
        scale = ic * float(np.std(forward)) / np.sqrt(1.0 - ic**2)
        if config.signal_front_loaded:
            drift[start + 1] += scale * z
        else:
            drift[start + 1 : stop + 1] += scale * z / (stop - start)
    return characteristic, drift


def _events(
    config: MarketConfig, n_days: int, idio_vol: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Events with New York clock times and the reaction they add to returns."""
    years = n_days / TRADING_DAYS_PER_YEAR
    counts = rng.poisson(config.events_per_year * years, config.n_assets)
    total = int(counts.sum())
    events = np.empty(total, dtype=EVENT_DTYPE)
    events["asset"] = np.repeat(np.arange(config.n_assets), counts)
    events["day"] = rng.integers(0, n_days, total)
    kind = rng.choice(3, size=total, p=[0.3, 0.3, 0.4])
    pre_open = rng.integers(6 * 60, MINUTES_MARKET_OPEN, total)
    intraday = rng.integers(MINUTES_MARKET_OPEN, MINUTES_MARKET_CLOSE, total)
    after_close = rng.integers(MINUTES_MARKET_CLOSE, 20 * 60, total)
    events["minutes"] = np.choose(kind, [pre_open, intraday, after_close])
    events["surprise"] = rng.standard_normal(total)
    events["reaction_day"] = events["day"] + (events["minutes"] >= MINUTES_MARKET_CLOSE)
    reaction = np.zeros((n_days, config.n_assets))
    inside = events["reaction_day"] < n_days
    np.add.at(
        reaction,
        (events["reaction_day"][inside], events["asset"][inside]),
        config.event_reaction_vol * idio_vol[events["asset"][inside]] * events["surprise"][inside],
    )
    order = np.lexsort((events["minutes"], events["day"], events["asset"]))
    return events[order], reaction


def _delistings(config: MarketConfig, returns: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Index of the delisting day per asset (-1 if it survives); losers delist more often."""
    n_days, n_assets = returns.shape
    log_wealth = np.cumsum(np.log1p(np.clip(returns, -0.99, None)), axis=0)
    trailing = np.zeros_like(log_wealth)
    window = TRADING_DAYS_PER_YEAR
    trailing[window:] = np.expm1(log_wealth[window:] - log_wealth[:-window])
    hazard = (config.delisting_rate_annual / TRADING_DAYS_PER_YEAR) * np.exp(
        config.delisting_loser_sensitivity * np.maximum(0.0, -trailing)
    )
    hazard[:window] = 0.0
    hits = rng.random((n_days, n_assets)) < hazard
    first = np.argmax(hits, axis=0)
    result: np.ndarray = np.where(hits.any(axis=0), first, -1)
    return result


def _add_distress(returns: np.ndarray, delisting_day: np.ndarray, config: MarketConfig) -> None:
    """Spread a total log decline of ``distress_decline`` over the days before each delisting."""
    daily = np.expm1(config.distress_decline / config.distress_days)
    for asset in np.flatnonzero(delisting_day >= 0):
        end = int(delisting_day[asset])
        start = max(0, end - config.distress_days)
        returns[start:end, asset] = (1 + returns[start:end, asset]) * (1 + daily) - 1


def _top_asset_of_block(characteristic: np.ndarray, alive: np.ndarray, start: int) -> int:
    scores = np.where(alive[start], characteristic[start], -np.inf)
    return int(np.argmax(scores))


def _defect_block(dates: np.ndarray, block_starts: np.ndarray, year: int) -> int:
    years = dates[block_starts].astype("datetime64[Y]").astype(int) + 1970
    candidates = np.flatnonzero(years == year)
    if candidates.size < 2:
        raise ValueError(f"defect_year {year} is outside the market dates")
    return int(candidates[candidates.size // 2])


def generate_market(config: MarketConfig, seed: int) -> SyntheticMarket:
    """Generate a synthetic market from ``config`` and ``seed``."""
    rng = np.random.default_rng(seed)
    dates = business_days(config.start, config.end)
    n_days, n_assets = dates.size, config.n_assets
    market, relative_vol = _market_factor(config, n_days, rng)
    betas = rng.normal(config.beta_mean, config.beta_std, n_assets)
    sectors = rng.integers(0, config.n_sectors, n_assets)
    sector_returns = standard_t(rng, config.tail_degrees_of_freedom, (n_days, config.n_sectors))
    sector_returns *= config.sector_vol_annual / np.sqrt(TRADING_DAYS_PER_YEAR)
    idio_vol = rng.uniform(*config.idio_vol_annual_range, n_assets) / np.sqrt(TRADING_DAYS_PER_YEAR)
    base = (
        betas[None, :] * market[:, None]
        + sector_returns[:, sectors]
        + _idiosyncratic(config, n_days, idio_vol, relative_vol, rng)
    )
    events, reaction = _events(config, n_days, idio_vol, rng)
    base += reaction
    block_starts = np.arange(0, n_days, config.signal_horizon)
    characteristic, drift = _plant_characteristic(config, base, dates, block_starts, rng)
    returns = base + drift

    defects: dict[str, tuple[int, int]] = {}
    alive_before = np.ones((n_days, n_assets), dtype=bool)
    if config.jump_size:
        block = _defect_block(dates, block_starts, config.defect_year)
        start = int(block_starts[block])
        asset = _top_asset_of_block(characteristic, alive_before, start)
        day = start + config.signal_horizon // 2
        returns[day, asset] = (1 + returns[day, asset]) * (1 + config.jump_size) - 1
        defects["jump"] = (day, asset)

    delisting_day = _delistings(config, returns, rng)
    if "jump" in defects:
        delisting_day[defects["jump"][1]] = -1
    alive = (
        np.arange(n_days)[:, None] < np.where(delisting_day >= 0, delisting_day, n_days)[None, :]
    )
    listed = delisting_day >= 0
    if config.distress_decline:
        _add_distress(returns, delisting_day, config)
    returns[delisting_day[listed], np.flatnonzero(listed)] = config.delisting_return
    after = (
        np.arange(n_days)[:, None] > np.where(delisting_day >= 0, delisting_day, n_days)[None, :]
    )
    returns[after] = np.nan
    characteristic[~alive] = np.nan
    secondary = returns.copy()

    if config.price_error_size:
        block = _defect_block(dates, block_starts, config.defect_year)
        while True:
            start = int(block_starts[block])
            asset = _top_asset_of_block(characteristic, alive, start)
            day = int(block_starts[block + 1])
            if alive[day, asset] and alive[day + 1, asset]:
                break
            block += 1
        returns[day, asset] = (1 + returns[day, asset]) * (1 + config.price_error_size) - 1
        returns[day + 1, asset] = (1 + returns[day + 1, asset]) / (1 + config.price_error_size) - 1
        defects["price_error"] = (day, asset)

    cost_bps = config.base_cost_bps * idio_vol / float(np.median(idio_vol))
    return SyntheticMarket(
        config=config,
        seed=seed,
        dates=dates,
        asset_ids=tuple(f"S{index:03d}" for index in range(n_assets)),
        returns=returns,
        secondary_returns=secondary,
        alive=alive,
        delisting_day=delisting_day,
        market_factor=market,
        betas=betas,
        sectors=sectors,
        idio_vol=idio_vol,
        cost_bps=cost_bps,
        characteristic=characteristic,
        block_starts=block_starts,
        events=events,
        defects=defects,
    )
