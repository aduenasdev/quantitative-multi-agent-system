from __future__ import annotations

import time
from dataclasses import replace
from datetime import date

import numpy as np
import pytest
from scipy import stats

from qmas.market import MarketConfig, SyntheticMarket, generate_market
from qmas.market.generator import MINUTES_MARKET_CLOSE, business_days
from qmas.stats.information import cross_sectional_rank_ic

SMALL = MarketConfig(n_assets=60, start=date(2016, 1, 4), end=date(2020, 12, 31))


def block_rank_ic(market: SyntheticMarket) -> np.ndarray:
    """Rank IC of the characteristic against each block's forward return."""
    horizon = market.config.signal_horizon
    starts = market.block_starts[market.block_starts + horizon < market.n_days]
    forward = np.array([np.nansum(market.returns[s + 1 : s + horizon + 1], axis=0) for s in starts])
    forward = np.where(market.alive[starts + horizon], forward, np.nan)
    return cross_sectional_rank_ic(market.characteristic[starts], forward, min_names=20)


def test_same_seed_same_market_and_different_seed_differs() -> None:
    first, second = generate_market(SMALL, 3), generate_market(SMALL, 3)
    np.testing.assert_array_equal(first.returns, second.returns)
    other = generate_market(SMALL, 4)
    assert not np.allclose(np.nan_to_num(first.returns), np.nan_to_num(other.returns))


def test_shapes_and_identifiers() -> None:
    market = generate_market(SMALL, 1)
    assert market.returns.shape == (market.n_days, 60)
    assert market.dates.size == business_days(SMALL.start, SMALL.end).size
    assert market.asset_ids[0] == "S000"
    assert market.block_starts[0] == 0
    assert np.all(np.diff(market.block_starts) == SMALL.signal_horizon)
    assert market.block_of_day()[SMALL.signal_horizon] == 1


def test_fat_tails_and_realistic_basket_correlation() -> None:
    market = generate_market(MarketConfig(), 100)
    pooled = market.returns[np.isfinite(market.returns)]
    assert stats.kurtosis(pooled, fisher=False) > 5
    order = np.random.default_rng(0).permutation(market.n_assets)
    first = np.nanmean(market.returns[:, order[:40]], axis=1)
    second = np.nanmean(market.returns[:, order[40:80]], axis=1)
    assert 0.8 < np.corrcoef(first, second)[0, 1] < 0.95


def test_delistings_end_with_the_delisting_return_and_hit_losers() -> None:
    market = generate_market(MarketConfig(), 102)
    delisted = np.flatnonzero(market.delisting_day >= 0)
    assert 0.05 < delisted.size / market.n_assets < 0.35
    for asset in delisted:
        day = market.delisting_day[asset]
        assert market.returns[day, asset] == pytest.approx(MarketConfig().delisting_return)
        assert np.isnan(market.returns[day + 1 :, asset]).all()
        assert not market.alive[day:, asset].any()
        assert market.alive[:day, asset].all()
    survivors = market.survivors()
    year_before = [
        np.nansum(market.returns[d - 252 : d, a])
        for a, d in zip(delisted, market.delisting_day[delisted], strict=True)
    ]
    survivor_years = np.nansum(market.returns[-252:, survivors], axis=0)
    assert float(np.mean(year_before)) < float(np.mean(survivor_years))


@pytest.mark.parametrize("ic", [0.0, 0.02, 0.04, 0.08])
def test_planted_ic_is_recovered(ic: float) -> None:
    config = MarketConfig(planted_ic=ic)
    measured = [
        float(np.nanmean(block_rank_ic(generate_market(config, seed)))) for seed in range(10, 20)
    ]
    assert float(np.mean(measured)) == pytest.approx(ic, abs=0.006)


def test_signal_active_years_limits_the_signal() -> None:
    config = MarketConfig(planted_ic=0.08, signal_active_years=(2020, 2021))
    market = generate_market(config, 5)
    ic = block_rank_ic(market)
    starts = market.block_starts[: ic.size]
    years = market.dates[starts].astype("datetime64[Y]").astype(int) + 1970
    active = np.isin(years, (2020, 2021))
    assert float(np.nanmean(ic[active])) > 0.05
    assert abs(float(np.nanmean(ic[~active]))) < 0.03


def test_front_loaded_signal_moves_only_the_first_day() -> None:
    no_delistings = MarketConfig(delisting_rate_annual=0.0)
    base = generate_market(no_delistings, 6)
    loaded = generate_market(replace(no_delistings, planted_ic=0.08, signal_front_loaded=True), 6)
    difference = np.nan_to_num(loaded.returns) - np.nan_to_num(base.returns)
    changed_days = np.flatnonzero(np.abs(difference).sum(axis=1) > 1e-12)
    assert set(changed_days) <= set(base.block_starts + 1)


def test_reversal_strength_creates_negative_autocorrelation() -> None:
    market = generate_market(MarketConfig(reversal_strength=0.3), 7)
    idio = market.returns - market.betas[None, :] * market.market_factor[:, None]
    today, tomorrow = idio[:-1].ravel(), idio[1:].ravel()
    valid = np.isfinite(today) & np.isfinite(tomorrow)
    assert np.corrcoef(today[valid], tomorrow[valid])[0, 1] < -0.1


def test_event_reactions_land_on_the_reaction_day() -> None:
    market = generate_market(replace(SMALL, events_per_year=8.0), 8)
    events = market.events
    after_close = events["minutes"] >= MINUTES_MARKET_CLOSE
    assert np.all(events["reaction_day"][after_close] == events["day"][after_close] + 1)
    assert np.all(events["reaction_day"][~after_close] == events["day"][~after_close])
    assert {0, 1} == set(np.unique(after_close.astype(int)))


def test_jump_appears_in_both_sources_of_a_held_name() -> None:
    market = generate_market(MarketConfig(jump_size=1.5), 9)
    day, asset = market.defects["jump"]
    assert market.returns[day, asset] > 1.0
    assert market.secondary_returns[day, asset] == market.returns[day, asset]
    block = market.block_of_day()[day]
    start = market.block_starts[block]
    assert market.characteristic[start, asset] == np.nanmax(market.characteristic[start])


def test_price_error_only_in_the_primary_source() -> None:
    clean = generate_market(MarketConfig(), 11)
    faulty = generate_market(MarketConfig(price_error_size=0.6), 11)
    day, asset = faulty.defects["price_error"]
    assert day in set(faulty.block_starts)
    growth = (1 + faulty.returns[day : day + 2, asset]).prod()
    clean_growth = (1 + clean.returns[day : day + 2, asset]).prod()
    assert growth == pytest.approx(clean_growth)
    assert faulty.returns[day, asset] > clean.returns[day, asset] + 0.5
    np.testing.assert_array_equal(faulty.secondary_returns, clean.returns)


def test_costs_are_proportional_to_volatility() -> None:
    market = generate_market(SMALL, 12)
    ratio = market.cost_bps / market.idio_vol
    np.testing.assert_allclose(ratio, ratio[0])
    assert float(np.median(market.cost_bps)) == pytest.approx(SMALL.base_cost_bps)


def test_default_market_is_fast() -> None:
    started = time.perf_counter()
    generate_market(MarketConfig(), 13)
    assert time.perf_counter() - started < 2.0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"n_assets": 5}, "n_assets"),
        ({"end": date(2015, 1, 1)}, "end"),
        ({"planted_ic": 1.0}, "planted_ic"),
        ({"signal_horizon": 0}, "signal_horizon"),
        ({"garch_alpha": 0.5, "garch_beta": 0.5}, "GARCH"),
        ({"tail_degrees_of_freedom": 2.0}, "tail"),
    ],
)
def test_invalid_config_is_rejected(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(MarketConfig(), **changes)  # type: ignore[arg-type]


def test_defect_year_outside_the_dates_is_rejected() -> None:
    with pytest.raises(ValueError, match="defect_year"):
        generate_market(replace(SMALL, jump_size=1.0, defect_year=2030), 1)
