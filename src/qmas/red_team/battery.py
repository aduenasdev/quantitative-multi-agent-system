"""Run a list of attacks on a claim and aggregate the verdict."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from qmas.contracts.verdict import AttackResult, RedTeamReport, aggregate_verdict
from qmas.red_team import part_one, part_two
from qmas.red_team.context import AttackContext

Attack = Callable[[AttackContext], AttackResult]

PART_ONE: tuple[Attack, ...] = (
    part_one.look_ahead,
    part_one.survivorship,
    part_one.costs,
    part_one.selection_bias,
    part_one.placebo,
    part_one.power,
)

PART_TWO: tuple[Attack, ...] = (
    part_two.factor_exposure,
    part_two.regime,
    part_two.calendar,
    part_two.concentration,
    part_two.data_source,
)

FULL_BATTERY: tuple[Attack, ...] = PART_ONE + PART_TWO


def run_battery(context: AttackContext, attacks: Sequence[Attack]) -> RedTeamReport:
    """Run ``attacks`` in order and combine their outcomes into a verdict."""
    results = tuple(attack(context) for attack in attacks)
    claimed = context.claimed_sharpe
    return RedTeamReport(
        verdict=aggregate_verdict(results),
        claimed_sharpe=claimed,
        # Rule: RULE-SANITY-01
        suspicious=claimed > context.thresholds.suspicious_sharpe,
        attacks=results,
    )
