"""Attacks A1-A5 and A10: leakage, survivorship, costs, selection bias, placebo and power."""

from __future__ import annotations

import numpy as np
from scipy import stats

from qmas.backtest import run_backtest
from qmas.contracts.verdict import AttackOutcome, AttackResult, Severity
from qmas.market.generator import TRADING_DAYS_PER_YEAR
from qmas.market.signals import compute_signal
from qmas.red_team.context import AttackContext
from qmas.stats.overfitting import probability_of_backtest_overfitting
from qmas.stats.sharpe import (
    deflated_sharpe_ratio,
    minimum_track_record_length,
    probabilistic_sharpe_ratio,
    return_moments,
)

ANNUALISATION = float(np.sqrt(TRADING_DAYS_PER_YEAR))


def no_edge(attack_id: str, name: str, severity: Severity, claimed: float) -> AttackResult:
    """Return the inconclusive result of an attack on a claim without a positive edge."""
    return AttackResult(
        attack_id=attack_id,
        name=name,
        severity=severity,
        outcome=AttackOutcome.INCONCLUSIVE,
        metrics={"claimed_sharpe": claimed},
        message="no positive edge to attack",
    )


def _outcome(failed: bool) -> AttackOutcome:
    return AttackOutcome.FAILED if failed else AttackOutcome.PASSED


def look_ahead(context: AttackContext) -> AttackResult:
    """A1: trade one day later than claimed; a real edge loses little, look-ahead loses it all."""
    name, severity = "look-ahead leakage", Severity.FATAL
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A1", name, severity, claimed)
    delayed = context.rerun(execution_delay=context.strategy.execution_delay + 1).sharpe()
    retention = delayed / claimed
    failed = retention < context.thresholds.delay_min_retention
    return AttackResult(
        attack_id="A1",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={"claimed_sharpe": claimed, "delayed_sharpe": delayed, "retention": retention},
        message=(
            f"one day of delay keeps {retention:.0%} of the Sharpe ratio"
            + (": the edge needs information from the future" if failed else "")
        ),
    )


def survivorship(context: AttackContext) -> AttackResult:
    """A2: re-run on the point-in-time universe, delisted names included."""
    name, severity = "survivorship bias", Severity.FATAL
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A2", name, severity, claimed)
    point_in_time = context.rerun(universe="point_in_time").sharpe()
    gap = claimed - point_in_time
    limits = context.thresholds
    failed = gap > max(limits.survivorship_max_gap, limits.survivorship_max_relative_gap * claimed)
    return AttackResult(
        attack_id="A2",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={"claimed_sharpe": claimed, "point_in_time_sharpe": point_in_time, "gap": gap},
        message=f"point-in-time universe Sharpe {point_in_time:.2f} against {claimed:.2f} claimed",
    )


def costs(context: AttackContext) -> AttackResult:
    """A3: charge volatility-dependent costs per name instead of the claimed costs."""
    name, severity = "trading costs", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A3", name, severity, claimed)
    realistic = context.rerun(cost_model="per_name")
    net = realistic.sharpe()
    retention = net / claimed
    failed = net <= 0 or retention < context.thresholds.cost_min_retention
    return AttackResult(
        attack_id="A3",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={
            "claimed_sharpe": claimed,
            "net_sharpe": net,
            "retention": retention,
            "annual_turnover": float(realistic.turnover.sum() / realistic.dates.size)
            * TRADING_DAYS_PER_YEAR,
        },
        message=f"with realistic costs the Sharpe ratio is {net:.2f}",
    )


def selection_bias(context: AttackContext) -> AttackResult:
    """A4: deflate the Sharpe ratio by every trial (RULE-TRIALS-01) and measure PBO."""
    name, severity = "selection bias", Severity.SERIOUS
    returns = context.claim.net_returns
    moments = return_moments(returns)
    limits = context.thresholds
    alone = probabilistic_sharpe_ratio(
        moments.sharpe_ratio, 0.0, moments.n_observations, moments.skewness, moments.kurtosis
    )
    trials = context.trials
    if trials.returns is not None and trials.returns.shape[1] >= 2:
        deviations = trials.returns.std(axis=0, ddof=1)
        trial_sharpes = trials.returns.mean(axis=0) / np.where(deviations > 0, deviations, np.inf)
        variance = float(np.var(trial_sharpes, ddof=1))
    else:
        variance = 1.0 / moments.n_observations
    deflated = deflated_sharpe_ratio(
        moments.sharpe_ratio,
        moments.n_observations,
        trials.n_trials,
        variance,
        moments.skewness,
        moments.kurtosis,
    )
    metrics = {
        "probabilistic_sharpe": alone,
        "deflated_sharpe": deflated,
        "n_trials": float(trials.n_trials),
    }
    overfit = False
    if trials.returns is not None and trials.returns.shape[1] >= 2:
        pbo = probability_of_backtest_overfitting(trials.returns, n_blocks=10).probability
        metrics["overfitting_probability"] = pbo
        overfit = pbo > limits.max_overfitting_probability
    if alone < limits.min_deflated_sharpe and not overfit:
        return AttackResult(
            attack_id="A4",
            name=name,
            severity=severity,
            outcome=AttackOutcome.INCONCLUSIVE,
            metrics=metrics,
            message="not significant even before deflation",
        )
    failed = overfit or deflated < limits.min_deflated_sharpe
    return AttackResult(
        attack_id="A4",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics=metrics,
        message=f"deflated Sharpe {deflated:.2f} over {trials.n_trials} trial(s)",
    )


def shuffle_across_names(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Permute each day's finite signal values across the names that have one."""
    valid = np.isfinite(signal)
    keys = rng.random(signal.shape)
    keys[~valid] = 2.0
    source = np.argsort(keys, axis=1)
    target = np.argsort(~valid, axis=1, kind="stable")
    take = np.arange(signal.shape[1])[None, :] < valid.sum(axis=1)[:, None]
    rows = np.nonzero(take)[0]
    shuffled = signal.copy()
    shuffled[rows, target[take]] = signal[rows, source[take]]
    return shuffled


def placebo(context: AttackContext) -> AttackResult:
    """A5: compare the claim with the same strategy on signals shuffled across names."""
    name, severity = "placebo", Severity.SERIOUS
    claimed = context.claimed_sharpe
    if claimed <= 0:
        return no_edge("A5", name, severity, claimed)
    rng = np.random.default_rng([context.seed, 5])
    signal = compute_signal(
        context.strategy.signal, context.market, context.strategy.signal_parameters
    )
    runs = context.thresholds.placebo_runs
    placebo_sharpes = np.array(
        [
            run_backtest(
                context.market, context.strategy, shuffle_across_names(signal, rng)
            ).sharpe()
            for _ in range(runs)
        ]
    )
    p_value = float((np.sum(placebo_sharpes >= claimed) + 1) / (runs + 1))
    failed = p_value > context.thresholds.max_p_value
    return AttackResult(
        attack_id="A5",
        name=name,
        severity=severity,
        outcome=_outcome(failed),
        metrics={
            "claimed_sharpe": claimed,
            "p_value": p_value,
            "placebo_mean_sharpe": float(placebo_sharpes.mean()),
            "placebo_95th_sharpe": float(np.quantile(placebo_sharpes, 0.95)),
        },
        message=f"placebo p-value {p_value:.3f} over {runs} shuffles",
    )


def power(context: AttackContext) -> AttackResult:
    """A10: measure whether the claim is significant and how long a record it would need."""
    moments = return_moments(context.claim.net_returns)
    limits = context.thresholds
    psr = probabilistic_sharpe_ratio(
        moments.sharpe_ratio, 0.0, moments.n_observations, moments.skewness, moments.kurtosis
    )
    z = float(stats.norm.ppf(limits.min_probabilistic_sharpe) + stats.norm.ppf(limits.power))
    minimum_detectable = z / np.sqrt(moments.n_observations - 1) * ANNUALISATION
    metrics = {
        "probabilistic_sharpe": psr,
        "n_observations": float(moments.n_observations),
        "minimum_detectable_sharpe": float(minimum_detectable),
    }
    if moments.sharpe_ratio > 0:
        metrics["minimum_track_record_days"] = minimum_track_record_length(
            moments.sharpe_ratio,
            0.0,
            moments.skewness,
            moments.kurtosis,
            limits.min_probabilistic_sharpe,
        )
    significant = psr >= limits.min_probabilistic_sharpe
    return AttackResult(
        attack_id="A10",
        name="statistical power",
        severity=Severity.EVIDENCE,
        outcome=AttackOutcome.PASSED if significant else AttackOutcome.INCONCLUSIVE,
        metrics=metrics,
        message=(
            f"probabilistic Sharpe {psr:.2f}; detectable Sharpe at {limits.power:.0%} power is "
            f"{minimum_detectable:.2f}"
        ),
    )
