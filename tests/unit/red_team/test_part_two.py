from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date

import pytest

from qmas.backtest import StrategySpec
from qmas.contracts.verdict import AttackOutcome, AttackResult, Verdict
from qmas.market import MarketConfig, generate_market
from qmas.red_team import (
    FULL_BATTERY,
    AttackContext,
    BatteryThresholds,
    TrialSet,
    part_two,
    run_battery,
)

DESIGN = {"start": date(2016, 1, 4), "end": date(2021, 12, 31)}
QUICK = BatteryThresholds(placebo_runs=30)


def context(seed: int, market: dict[str, object], **strategy: object) -> AttackContext:
    the_market = generate_market(replace(MarketConfig(), **market), seed)  # type: ignore[arg-type]
    base = StrategySpec(signal="planted_characteristic", cost_bps=10.0, **DESIGN)  # type: ignore[arg-type]
    return AttackContext(the_market, replace(base, **strategy), TrialSet(), QUICK, seed)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def clean() -> AttackContext:
    return context(1000, {"planted_ic": 0.08})


@pytest.fixture(scope="module")
def losing() -> AttackContext:
    for seed in range(1000, 1010):
        candidate = context(seed, {})
        if candidate.claimed_sharpe <= 0:
            return candidate
    raise AssertionError("no losing claim found")


ATTACKS: list[Callable[[AttackContext], AttackResult]] = [
    part_two.factor_exposure,
    part_two.regime,
    part_two.calendar,
    part_two.concentration,
    part_two.data_source,
]


@pytest.mark.parametrize("attack", ATTACKS)
def test_clean_signal_passes(
    clean: AttackContext, attack: Callable[[AttackContext], AttackResult]
) -> None:
    assert attack(clean).outcome is AttackOutcome.PASSED


@pytest.mark.parametrize("attack", ATTACKS)
def test_losing_claim_is_inconclusive(
    losing: AttackContext, attack: Callable[[AttackContext], AttackResult]
) -> None:
    assert attack(losing).outcome is AttackOutcome.INCONCLUSIVE


def test_a6_catches_a_disguised_market_bet() -> None:
    bet = context(
        1000,
        {"market_drift_annual": 0.20, "market_vol_annual": 0.12},
        signal="beta_exposure",
        portfolio="long_only",
    )
    attack = part_two.factor_exposure(bet)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["market_beta"] > 1.2


def test_a7_catches_a_regime_limited_signal() -> None:
    limited = context(1002, {"planted_ic": 0.08, "signal_active_years": (2020, 2021)})
    attack = part_two.regime(limited)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["subperiod_3_sharpe"] > attack.metrics["subperiod_1_sharpe"]


def test_a8_catches_a_single_day_signal() -> None:
    front = context(1000, {"planted_ic": 0.08, "signal_front_loaded": True})
    attack = part_two.calendar(front)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["retention"] < 0.25


def test_a8_is_inconclusive_for_daily_rebalancing() -> None:
    daily = context(1000, {"planted_ic": 0.08}, horizon_days=1, rebalance_every_days=1)
    assert part_two.calendar(daily).outcome is AttackOutcome.INCONCLUSIVE


def test_a9_catches_a_single_name_jump() -> None:
    jump = context(1001, {"jump_size": 3.0}, quantile=0.025)
    attack = part_two.concentration(jump)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["top_name_share"] > 0.5


def test_a13_catches_a_bad_price() -> None:
    error = context(1001, {"price_error_size": 2.0}, quantile=0.025)
    attack = part_two.data_source(error)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["secondary_sharpe"] < attack.metrics["claimed_sharpe"]


def test_full_battery_on_a_clean_signal(clean: AttackContext) -> None:
    report = run_battery(clean, FULL_BATTERY)
    ids = [attack.attack_id for attack in report.attacks]
    assert ids == ["A1", "A2", "A3", "A4", "A5", "A10", "A6", "A7", "A8", "A9", "A13"]
    assert report.verdict is Verdict.SURVIVES
