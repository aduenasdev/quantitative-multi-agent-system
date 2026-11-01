"""Attacks A6-A9 and A13: factor exposure, regime, calendar, concentration and data source."""

from __future__ import annotations

import numpy as np

from qmas.contracts.verdict import AttackOutcome, AttackResult, Severity
from qmas.red_team.context import AttackContext
from qmas.red_team.part_one import ANNUALISATION, no_edge
from qmas.stats.information import newey_west_t_statistic
from qmas.stats.sharpe import probabilistic_sharpe_ratio, return_moments


def _outcome(failed: bool) -> AttackOutcome:
    return AttackOutcome.FAILED if failed else AttackOutcome.PASSED


def _annual_sharpe(returns: np.ndarray) -> float:
    deviation = float(np.std(returns, ddof=1))
    return float(np.mean(returns) / deviation * ANNUALISATION) if deviation > 0 else 0.0


def factor_exposure(context: AttackContext) -> AttackResult:
    """A6: remove the market exposure and test what is left."""
    name, severity = "factor exposure", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A6", name, severity, claimed)
    claim = context.claim
    market_returns = context.market.market_factor[np.isin(context.market.dates, claim.dates)]
    beta, _ = np.polyfit(market_returns, claim.net_returns, 1)
    alpha_returns = claim.net_returns - beta * market_returns
    alpha_sharpe = _annual_sharpe(alpha_returns)
    alpha_t = newey_west_t_statistic(alpha_returns)
    moments = return_moments(claim.net_returns)
    significant = (
        probabilistic_sharpe_ratio(
            moments.sharpe_ratio, 0.0, moments.n_observations, moments.skewness, moments.kurtosis
        )
        >= context.thresholds.min_probabilistic_sharpe
    )
    limits = context.thresholds
    failed = alpha_sharpe < limits.factor_min_retention * claimed or (
        significant and alpha_t < limits.factor_min_t_statistic
    )
    return AttackResult(
        attack_id="A6",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={
            "claimed_sharpe": claimed,
            "market_beta": float(beta),
            "alpha_sharpe": alpha_sharpe,
            "alpha_t_statistic": alpha_t,
        },
        message=f"beta {beta:.2f}; alpha Sharpe {alpha_sharpe:.2f} (t = {alpha_t:.2f})",
    )


def regime(context: AttackContext) -> AttackResult:
    """A7: the edge must show up in every sub-period, not in one of them."""
    name, severity = "regime dependence", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A7", name, severity, claimed)
    limits = context.thresholds
    parts = np.array_split(context.claim.net_returns, limits.regime_subperiods)
    sharpes = [_annual_sharpe(part) for part in parts]
    pnl = np.array([part.sum() for part in parts])
    share = float(pnl.max() / pnl.sum()) if pnl.sum() > 0 else float("inf")
    failed = min(sharpes) <= 0 or share > limits.regime_max_share
    metrics = {f"subperiod_{index + 1}_sharpe": value for index, value in enumerate(sharpes)}
    metrics["best_subperiod_share"] = share
    return AttackResult(
        attack_id="A7",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics=metrics,
        message=f"sub-period Sharpe ratios {', '.join(f'{s:.2f}' for s in sharpes)}",
    )


def calendar(context: AttackContext) -> AttackResult:
    """A8: rebalance on every other day of the cycle; a real edge is not tied to one date."""
    name, severity = "rebalancing calendar", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A8", name, severity, claimed)
    cycle = context.strategy.rebalance_every_days
    if cycle == 1:
        return AttackResult(
            attack_id="A8",
            name=name,
            severity=severity,
            outcome=AttackOutcome.INCONCLUSIVE,
            metrics={"claimed_sharpe": claimed},
            message="daily rebalancing has a single calendar",
        )
    offsets = [offset for offset in range(cycle) if offset != context.strategy.offset]
    others = [context.rerun(offset=offset).sharpe() for offset in offsets]
    retention = float(np.mean(others)) / claimed
    failed = retention < context.thresholds.calendar_min_retention
    return AttackResult(
        attack_id="A8",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={
            "claimed_sharpe": claimed,
            "mean_other_offset_sharpe": float(np.mean(others)),
            "worst_offset_sharpe": float(np.min(others)),
            "retention": retention,
        },
        message=f"the other {len(others)} calendars keep {retention:.0%} of the Sharpe ratio",
    )


def concentration(context: AttackContext) -> AttackResult:
    """A9: the edge must not come from a single name."""
    name, severity = "concentration", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A9", name, severity, claimed)
    contributions = context.claim.contributions
    top = int(np.argmax(contributions))
    total = float(contributions.sum())
    share = float(contributions[top] / total) if total > 0 else float("inf")
    without = context.rerun(excluded_assets=context.strategy.excluded_assets | {top}).sharpe()
    retention = without / claimed
    limits = context.thresholds
    failed = (
        share > limits.concentration_max_share or retention < limits.concentration_min_retention
    )
    return AttackResult(
        attack_id="A9",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={
            "claimed_sharpe": claimed,
            "top_name_share": share,
            "sharpe_without_top_name": without,
            "retention": retention,
        },
        message=(
            f"{context.market.asset_ids[top]} earns {share:.0%} of the PnL; without it the Sharpe "
            f"ratio is {without:.2f}"
        ),
    )


def data_source(context: AttackContext) -> AttackResult:
    """A13: re-run on an independent price source; a data error does not replicate."""
    name, severity = "second price source", Severity.FATAL
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A13", name, severity, claimed)
    secondary = context.rerun(price_source="secondary").sharpe()
    gap = claimed - secondary
    limits = context.thresholds
    failed = abs(gap) > limits.source_max_gap + limits.source_max_relative_gap * abs(claimed)
    return AttackResult(
        attack_id="A13",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={"claimed_sharpe": claimed, "secondary_sharpe": secondary, "gap": gap},
        message=f"second source Sharpe {secondary:.2f} against {claimed:.2f}",
    )
