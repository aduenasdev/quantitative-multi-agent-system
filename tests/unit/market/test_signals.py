from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from qmas.market import MarketConfig, SyntheticMarket, generate_market
from qmas.market.generator import MINUTES_MARKET_CLOSE
from qmas.market.signals import NEW_YORK_UTC_OFFSET_MINUTES, SIGNALS, compute_signal

CONFIG = MarketConfig(n_assets=50, start=date(2016, 1, 4), end=date(2019, 12, 31))


@pytest.fixture(scope="module")
def market() -> SyntheticMarket:
    return generate_market(CONFIG, 21)


@pytest.mark.parametrize("name", sorted(SIGNALS))
def test_every_signal_has_the_market_shape_and_hides_dead_assets(
    market: SyntheticMarket, name: str
) -> None:
    values = compute_signal(name, market, {})
    assert values.shape == market.returns.shape
    assert np.isnan(values[~market.alive]).all()


def test_unknown_signal_is_rejected(market: SyntheticMarket) -> None:
    with pytest.raises(KeyError, match="unknown signal 'magic'"):
        compute_signal("magic", market, {})


def test_parameter_types_are_checked(market: SyntheticMarket) -> None:
    with pytest.raises(TypeError, match="integer"):
        compute_signal("trailing_return", market, {"days": "252"})
    with pytest.raises(TypeError, match="boolean"):
        compute_signal("event_surprise", market, {"timestamps_as_utc": 1})
    with pytest.raises(ValueError, match="positive"):
        compute_signal("trailing_return", market, {"days": 0})


def test_honest_signals_do_not_change_when_the_future_changes(market: SyntheticMarket) -> None:
    cut = 400
    altered = generate_market(CONFIG, 21)
    altered.returns[cut + 1 :] = np.where(np.isfinite(altered.returns[cut + 1 :]), 0.0, np.nan)
    honest = ["short_term_reversal", "trailing_return", "beta_exposure", "planted_characteristic"]
    for name in honest:
        np.testing.assert_array_equal(
            compute_signal(name, market, {})[: cut + 1],
            compute_signal(name, altered, {})[: cut + 1],
        )
    leaky = compute_signal("future_return", market, {})[cut]
    assert not np.allclose(
        np.nan_to_num(leaky), np.nan_to_num(compute_signal("future_return", altered, {})[cut])
    )


def test_future_return_is_tomorrows_return(market: SyntheticMarket) -> None:
    values = compute_signal("future_return", market, {})
    alive_tomorrow = market.alive[10] & market.alive[11]
    np.testing.assert_allclose(values[10, alive_tomorrow], market.returns[11, alive_tomorrow])


def test_trailing_return_and_inversion(market: SyntheticMarket) -> None:
    values = compute_signal("trailing_return", market, {"days": 5})
    expected = np.prod(1 + market.returns[6:11, 0]) - 1
    assert values[10, 0] == pytest.approx(expected)
    inverted = compute_signal("trailing_return", market, {"days": 5, "invert": True})
    assert inverted[10, 0] == pytest.approx(-expected)
    assert np.isnan(values[:5]).all()


def test_random_characteristic_is_reproducible_and_block_constant(
    market: SyntheticMarket,
) -> None:
    first = compute_signal("random_characteristic", market, {"seed": 3})
    np.testing.assert_array_equal(
        first, compute_signal("random_characteristic", market, {"seed": 3})
    )
    assert not np.allclose(
        np.nan_to_num(first),
        np.nan_to_num(compute_signal("random_characteristic", market, {"seed": 4})),
    )
    block = slice(market.block_starts[1], market.block_starts[2])
    alive = market.alive[block].all(axis=0)
    assert np.all(first[block][:, alive] == first[market.block_starts[1], alive])


def test_beta_exposure_repeats_the_betas(market: SyntheticMarket) -> None:
    values = compute_signal("beta_exposure", market, {})
    np.testing.assert_allclose(values[0], market.betas)


def test_event_surprise_timing_and_the_time_zone_defect(market: SyntheticMarket) -> None:
    honest = compute_signal("event_surprise", market, {})
    buggy = compute_signal("event_surprise", market, {"timestamps_as_utc": True})
    events = market.events
    shifted = (events["minutes"] >= MINUTES_MARKET_CLOSE) & (
        events["minutes"] - NEW_YORK_UTC_OFFSET_MINUTES < MINUTES_MARKET_CLOSE
    )
    usable = (events["day"] + 1 < market.n_days) & market.alive[
        np.minimum(events["day"] + 1, market.n_days - 1), events["asset"]
    ]
    example = np.flatnonzero(shifted & usable)[0]
    day, asset = events["day"][example], events["asset"][example]
    assert np.isnan(honest[day, asset]) or honest[day, asset] != events["surprise"][example]
    assert honest[day + 1, asset] == events["surprise"][example]
    assert buggy[day, asset] == events["surprise"][example]
    known_honest = int(np.isfinite(honest).sum())
    assert known_honest > 0
    assert int(np.isfinite(buggy).sum()) == pytest.approx(known_honest, rel=0.05)
