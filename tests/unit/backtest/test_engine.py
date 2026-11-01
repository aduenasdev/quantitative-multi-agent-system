from __future__ import annotations

import time
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from qmas.backtest import StrategySpec, market_from_thesis, run_backtest, strategy_from_thesis
from qmas.market import MarketConfig, SyntheticMarket, generate_market
from tests.factories import make_thesis

DESIGN = {"start": date(2016, 1, 4), "end": date(2021, 12, 31)}


def planted(seed: int, ic: float = 0.08, **config: object) -> SyntheticMarket:
    return generate_market(replace(MarketConfig(planted_ic=ic), **config), seed)  # type: ignore[arg-type]


def strategy(**changes: object) -> StrategySpec:
    base = StrategySpec(signal="planted_characteristic", **DESIGN)  # type: ignore[arg-type]
    return replace(base, **changes)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def market() -> SyntheticMarket:
    return planted(31)


def test_long_short_weights_are_dollar_neutral(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy())
    assert result.n_rebalances == pytest.approx((result.dates.size - 1) / 21, abs=1)
    assert 0.3 * market.n_assets < result.average_names <= 0.4 * market.n_assets
    first_rebalance = result.turnover[1]
    assert first_rebalance == pytest.approx(2.0)


def test_long_only_weights_sum_to_one(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy(portfolio="long_only"))
    assert result.turnover[1] == pytest.approx(1.0)
    assert 0.15 * market.n_assets < result.average_names <= 0.2 * market.n_assets


def test_planted_signal_is_profitable_and_noise_is_not() -> None:
    strong = [run_backtest(planted(seed), strategy()).sharpe() for seed in range(40, 45)]
    noise = [run_backtest(planted(seed, ic=0.0), strategy()).sharpe() for seed in range(40, 48)]
    assert min(strong) > 1.0
    assert abs(float(np.mean(noise))) < 0.3


def test_costs_equal_turnover_times_cost(market: SyntheticMarket) -> None:
    gross = run_backtest(market, strategy())
    flat = run_backtest(market, strategy(cost_bps=25.0))
    np.testing.assert_allclose(gross.gross_returns, flat.gross_returns)
    np.testing.assert_allclose(flat.gross_returns - flat.net_returns, flat.turnover * 25e-4)
    per_name = run_backtest(market, strategy(cost_model="per_name"))
    charged = per_name.gross_returns - per_name.net_returns
    assert charged.sum() > 0
    assert per_name.sharpe() < per_name.sharpe(net=False)


def test_execution_delay_uses_older_signal(market: SyntheticMarket) -> None:
    on_time = run_backtest(market, strategy())
    delayed = run_backtest(market, strategy(execution_delay=1))
    assert delayed.sharpe() < on_time.sharpe()
    assert delayed.sharpe() > 0.5 * on_time.sharpe()


def test_look_ahead_signal_collapses_with_one_day_delay() -> None:
    market = planted(32, ic=0.0)
    leak = strategy(signal="future_return", horizon_days=1, rebalance_every_days=1)
    assert run_backtest(market, leak).sharpe() > 5
    assert abs(run_backtest(market, replace(leak, execution_delay=1)).sharpe()) < 1


def test_survivor_universe_only_holds_survivors(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy(universe="survivors"))
    dead = ~market.survivors()
    assert np.all(result.contributions[dead] == 0)
    full = run_backtest(market, strategy())
    assert np.any(full.contributions[dead] != 0)


def test_secondary_source_only_differs_with_a_price_error() -> None:
    clean = planted(33)
    np.testing.assert_allclose(
        run_backtest(clean, strategy()).gross_returns,
        run_backtest(clean, strategy(price_source="secondary")).gross_returns,
    )
    faulty = planted(33, price_error_size=0.6)
    difference = (
        run_backtest(faulty, strategy()).gross_returns
        - run_backtest(faulty, strategy(price_source="secondary")).gross_returns
    )
    assert np.count_nonzero(np.abs(difference) > 1e-12) <= 2


def test_excluded_assets_are_never_held(market: SyntheticMarket) -> None:
    full = run_backtest(market, strategy())
    top = int(np.argmax(np.abs(full.contributions)))
    reduced = run_backtest(market, strategy(excluded_assets=frozenset({top})))
    assert reduced.contributions[top] == 0


def test_offset_moves_the_rebalancing_days(market: SyntheticMarket) -> None:
    base = run_backtest(market, strategy())
    shifted = run_backtest(market, strategy(offset=5))
    assert np.flatnonzero(base.turnover)[0] == 1
    assert np.flatnonzero(shifted.turnover)[0] == 6
    assert shifted.sharpe() < base.sharpe()


def test_overlapping_tranches(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy(horizon_days=21, rebalance_every_days=7))
    assert result.strategy.tranches == 3
    assert result.turnover[1] == pytest.approx(2.0 / 3)
    assert result.sharpe() > 0


def test_window_limits_the_returns(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy(start=date(2018, 1, 1), end=date(2018, 12, 31)))
    assert str(result.dates[0]) >= "2018-01-01"
    assert str(result.dates[-1]) <= "2018-12-31"
    assert result.gross_returns.size == result.dates.size
    with pytest.raises(ValueError, match="overlap"):
        run_backtest(market, strategy(start=date(2030, 1, 1), end=date(2030, 12, 31)))


def test_sharpe_of_flat_returns_is_zero(market: SyntheticMarket) -> None:
    result = run_backtest(market, strategy(signal="beta_exposure", quantile=0.5))
    flat = replace(result, net_returns=np.zeros_like(result.net_returns))
    assert flat.sharpe() == 0.0
    assert result.returns(net=False) is result.gross_returns


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"end": date(2015, 1, 1)}, "end"),
        ({"horizon_days": 0}, "positive"),
        ({"horizon_days": 20, "rebalance_every_days": 7}, "multiple"),
        ({"offset": 21}, "offset"),
        ({"quantile": 0.6}, "quantile"),
        ({"execution_delay": -1}, "non-negative"),
    ],
)
def test_invalid_strategies_are_rejected(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        strategy(**changes)


def test_full_backtest_is_fast(market: SyntheticMarket) -> None:
    started = time.perf_counter()
    run_backtest(market, strategy(cost_model="per_name"))
    assert time.perf_counter() - started < 0.5


def test_strategy_and_market_from_thesis() -> None:
    thesis = make_thesis(
        data={"source": "synthetic", "seed": 3, "parameters": {"n_assets": 40, "planted_ic": 0.05}},
        portfolio={"kind": "long_only", "quantile": 0.1},
    )
    design, holdout = strategy_from_thesis(thesis), strategy_from_thesis(thesis, "holdout")
    assert (design.start, design.end) == (thesis.design_window.start, thesis.design_window.end)
    assert holdout.start == thesis.holdout_window.start
    assert design.portfolio == "long_only"
    assert design.quantile == 0.1
    market = market_from_thesis(thesis)
    assert market.n_assets == 40
    assert market.config.planted_ic == 0.05
    bad = make_thesis(data={"source": "synthetic", "seed": 3, "parameters": {"magic": 1}})
    with pytest.raises(ValueError, match="unknown market parameters: magic"):
        market_from_thesis(bad)
