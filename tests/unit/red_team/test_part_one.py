from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from qmas.backtest import StrategySpec, run_backtest
from qmas.contracts.verdict import (
    AttackOutcome,
    AttackResult,
    RedTeamReport,
    Severity,
    Verdict,
    aggregate_verdict,
)
from qmas.market import MarketConfig, SyntheticMarket, generate_market
from qmas.red_team import (
    PART_ONE,
    AttackContext,
    BatteryThresholds,
    TrialSet,
    part_one,
    run_battery,
)

DESIGN = {"start": date(2016, 1, 4), "end": date(2021, 12, 31)}
QUICK = BatteryThresholds(placebo_runs=30)
SEED = 1000


def market(**changes: object) -> SyntheticMarket:
    return generate_market(replace(MarketConfig(), **changes), SEED)  # type: ignore[arg-type]


def strategy(**changes: object) -> StrategySpec:
    base = StrategySpec(signal="planted_characteristic", cost_bps=10.0, **DESIGN)  # type: ignore[arg-type]
    return replace(base, **changes)  # type: ignore[arg-type]


def context(
    the_market: SyntheticMarket, the_strategy: StrategySpec, trials: TrialSet | None = None
) -> AttackContext:
    return AttackContext(the_market, the_strategy, trials or TrialSet(), QUICK, SEED)


@pytest.fixture(scope="module")
def clean() -> AttackContext:
    return context(market(planted_ic=0.08), strategy())


@pytest.fixture(scope="module")
def losing() -> AttackContext:
    the_market = market()
    the_strategy = strategy(signal="trailing_return", signal_parameters={"invert": False})
    ctx = context(the_market, the_strategy)
    if ctx.claimed_sharpe > 0:
        ctx = context(the_market, replace(the_strategy, signal_parameters={"invert": True}))
    assert ctx.claimed_sharpe <= 0
    return ctx


def result(severity: Severity, outcome: AttackOutcome) -> AttackResult:
    return AttackResult(attack_id="A1", name="x", severity=severity, outcome=outcome)


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        (
            [(Severity.FATAL, AttackOutcome.FAILED), (Severity.SERIOUS, AttackOutcome.FAILED)],
            Verdict.BROKEN,
        ),
        (
            [
                (Severity.SERIOUS, AttackOutcome.FAILED),
                (Severity.EVIDENCE, AttackOutcome.INCONCLUSIVE),
            ],
            Verdict.WOUNDED,
        ),
        (
            [
                (Severity.FATAL, AttackOutcome.PASSED),
                (Severity.EVIDENCE, AttackOutcome.INCONCLUSIVE),
            ],
            Verdict.NOT_PROVABLE,
        ),
        (
            [
                (Severity.FATAL, AttackOutcome.INCONCLUSIVE),
                (Severity.EVIDENCE, AttackOutcome.PASSED),
            ],
            Verdict.SURVIVES,
        ),
    ],
)
def test_aggregate_verdict(
    outcomes: list[tuple[Severity, AttackOutcome]], verdict: Verdict
) -> None:
    assert aggregate_verdict(tuple(result(s, o) for s, o in outcomes)) is verdict


def test_report_lookup() -> None:
    report = RedTeamReport(
        verdict=Verdict.BROKEN,
        claimed_sharpe=1.0,
        suspicious=False,
        attacks=(result(Severity.FATAL, AttackOutcome.FAILED),),
    )
    assert report.attack("A1").outcome is AttackOutcome.FAILED
    assert report.failed() == ("A1",)
    with pytest.raises(KeyError):
        report.attack("A9")


def test_clean_signal_survives_part_one(clean: AttackContext) -> None:
    report = run_battery(clean, PART_ONE)
    assert report.verdict is Verdict.SURVIVES
    assert report.suspicious
    assert [a.attack_id for a in report.attacks] == ["A1", "A2", "A3", "A4", "A5", "A10"]


def test_battery_is_deterministic(clean: AttackContext) -> None:
    first, second = run_battery(clean, PART_ONE), run_battery(clean, PART_ONE)
    assert first == second


@pytest.mark.parametrize(
    "attack", [part_one.look_ahead, part_one.survivorship, part_one.costs, part_one.placebo]
)
def test_attacks_on_a_losing_claim_are_inconclusive(losing: AttackContext, attack: object) -> None:
    outcome = attack(losing).outcome  # type: ignore[operator]
    assert outcome is AttackOutcome.INCONCLUSIVE


def test_a1_catches_look_ahead() -> None:
    leak = context(
        market(), strategy(signal="future_return", horizon_days=1, rebalance_every_days=1)
    )
    attack = part_one.look_ahead(leak)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["retention"] < 0.1


def test_a2_catches_survivorship() -> None:
    biased = context(
        market(delisting_rate_annual=0.03, distress_decline=-0.7),
        strategy(
            signal="trailing_return", signal_parameters={"invert": True}, universe="survivors"
        ),
    )
    attack = part_one.survivorship(biased)
    assert attack.outcome is AttackOutcome.FAILED
    assert attack.metrics["point_in_time_sharpe"] < 0


def test_a3_catches_gross_only_edges(clean: AttackContext) -> None:
    reversal = context(
        market(reversal_strength=0.05),
        strategy(
            signal="short_term_reversal", horizon_days=1, rebalance_every_days=1, cost_bps=0.0
        ),
    )
    assert part_one.costs(reversal).outcome is AttackOutcome.FAILED
    assert part_one.costs(clean).outcome is AttackOutcome.PASSED


def test_a4_catches_the_best_of_many_noise_signals(clean: AttackContext) -> None:
    noise = market()
    trials = [
        strategy(signal="random_characteristic", signal_parameters={"seed": k}) for k in range(60)
    ]
    results = [run_backtest(noise, t) for t in trials]
    best = int(np.argmax([r.sharpe() for r in results]))
    trial_set = TrialSet(n_trials=60, returns=np.column_stack([r.net_returns for r in results]))
    selected = AttackContext(noise, trials[best], trial_set, QUICK, SEED, claimed=results[best])
    attack = part_one.selection_bias(selected)
    assert attack.outcome is not AttackOutcome.PASSED
    assert attack.metrics["deflated_sharpe"] < attack.metrics["probabilistic_sharpe"]
    assert "overfitting_probability" in attack.metrics
    assert part_one.selection_bias(clean).outcome is AttackOutcome.PASSED


def test_a4_is_inconclusive_without_significance(losing: AttackContext) -> None:
    assert part_one.selection_bias(losing).outcome is AttackOutcome.INCONCLUSIVE


def test_a5_rejects_a_lucky_noise_claim(clean: AttackContext) -> None:
    noise = context(market(), strategy())
    assert noise.claimed_sharpe > 0
    attack = part_one.placebo(noise)
    assert attack.outcome is AttackOutcome.FAILED
    assert part_one.placebo(clean).metrics["p_value"] <= QUICK.max_p_value


def test_a10_reports_power(clean: AttackContext, losing: AttackContext) -> None:
    strong = part_one.power(clean)
    assert strong.outcome is AttackOutcome.PASSED
    assert strong.metrics["minimum_track_record_days"] < strong.metrics["n_observations"]
    weak = part_one.power(losing)
    assert weak.outcome is AttackOutcome.INCONCLUSIVE
    assert "minimum_track_record_days" not in weak.metrics
    assert weak.metrics["minimum_detectable_sharpe"] > 0


def test_shuffle_keeps_values_and_gaps() -> None:
    signal = np.array([[1.0, 2.0, np.nan, 3.0], [np.nan, np.nan, 5.0, np.nan]])
    shuffled = part_one.shuffle_across_names(signal, np.random.default_rng(0))
    np.testing.assert_array_equal(np.isnan(shuffled), np.isnan(signal))
    assert sorted(shuffled[0][np.isfinite(shuffled[0])]) == [1.0, 2.0, 3.0]
    assert shuffled[1, 2] == 5.0


def test_trial_set_and_threshold_validation() -> None:
    with pytest.raises(ValueError, match="n_trials"):
        TrialSet(n_trials=0)
    with pytest.raises(ValueError, match="matrix"):
        TrialSet(n_trials=2, returns=np.zeros(5))
    assert BatteryThresholds().with_overrides(placebo_runs=5).placebo_runs == 5


def test_engine_rejects_a_misshaped_signal(clean: AttackContext) -> None:
    with pytest.raises(ValueError, match="shape"):
        run_backtest(clean.market, clean.strategy, np.zeros((3, 3)))
