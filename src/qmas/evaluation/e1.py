"""E1: measure how well the battery separates planted defects and noise from real signals.

Pre-registered pass criteria (from the evaluation plan of the battery):

* at least 95 % of defect claims are caught (verdict ``BROKEN`` or ``WOUNDED``);
* at most 10 % of pure-noise signals (planted IC 0) ``SURVIVES`` (the false positive rate);
* at least 80 % of planted signals whose expected Sharpe ratio is above the minimum detectable
  Sharpe ``SURVIVES``.

A defect case whose claimed Sharpe ratio is not positive is not a claim anyone would bring; it
is reported but left out of the first criterion. Thresholds are calibrated on
``CALIBRATION_SEEDS`` and the verdict is given on ``JUDGEMENT_SEEDS``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from pydantic import BaseModel, ConfigDict

from qmas.backtest import run_backtest
from qmas.contracts.verdict import Verdict
from qmas.evaluation.cases import (
    CALIBRATION_SEEDS,
    DESIGN_END,
    DESIGN_START,
    SIGNALS,
    TEMPLATES,
    CaseTemplate,
    build_context,
    claimed_strategy,
    market_config,
)
from qmas.market import generate_market
from qmas.market.generator import business_days
from qmas.red_team import FULL_BATTERY, BatteryThresholds, run_battery
from qmas.red_team.part_one import minimum_detectable_sharpe

MIN_DEFECTS_CAUGHT = 0.95
MAX_NOISE_SURVIVING = 0.10
MIN_SIGNALS_SURVIVING = 0.80
CAUGHT = frozenset({Verdict.BROKEN, Verdict.WOUNDED})


class CaseOutcome(BaseModel):
    """Verdict of one case on one seed."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    kind: str
    seed: int
    claimed_sharpe: float
    verdict: Verdict
    failed_attacks: tuple[str, ...]
    expected_attacks: tuple[str, ...]
    is_claim: bool
    caught: bool
    caught_by_expected: bool


class Criterion(BaseModel):
    """One pre-registered criterion and whether it was met."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float | None
    threshold: float
    passed: bool
    detail: str


class E1Report(BaseModel):
    """Full E1 result: every case, the confusion matrix and the criteria."""

    model_config = ConfigDict(frozen=True)

    seeds: tuple[int, ...]
    placebo_runs: int
    outcomes: tuple[CaseOutcome, ...]
    confusion: dict[str, dict[str, int]]
    minimum_detectable_sharpe: float
    expected_signal_sharpe: dict[str, float]
    criteria: tuple[Criterion, ...]

    @property
    def passed(self) -> bool:
        """Return whether every criterion was met."""
        return all(criterion.passed for criterion in self.criteria)


def evaluate_case(template: CaseTemplate, seed: int, thresholds: BatteryThresholds) -> CaseOutcome:
    """Run the full battery on one case and seed."""
    context = build_context(template, seed, thresholds)
    report = run_battery(context, FULL_BATTERY)
    failed = report.failed()
    is_claim = template.kind == "signal" or report.claimed_sharpe > 0
    return CaseOutcome(
        case_id=template.case_id,
        kind=template.kind,
        seed=seed,
        claimed_sharpe=report.claimed_sharpe,
        verdict=report.verdict,
        failed_attacks=failed,
        expected_attacks=template.expected_attacks,
        is_claim=is_claim,
        caught=report.verdict in CAUGHT,
        caught_by_expected=bool(set(failed) & set(template.expected_attacks)),
    )


def expected_signal_sharpe(template: CaseTemplate) -> float:
    """Mean claimed Sharpe ratio of a planted signal over the calibration seeds (no battery)."""
    strategy = claimed_strategy(template)
    config = market_config(template)
    return float(
        np.mean(
            [
                run_backtest(generate_market(config, seed), strategy).sharpe()
                for seed in CALIBRATION_SEEDS
            ]
        )
    )


def _rate(values: Sequence[bool]) -> float | None:
    return float(np.mean(values)) if values else None


def _criteria(outcomes: Sequence[CaseOutcome], above_mde: set[str]) -> tuple[Criterion, ...]:
    claims = [o for o in outcomes if o.kind == "defect" and o.is_claim]
    noise = [o for o in outcomes if o.case_id == SIGNALS[0].case_id]
    detectable = [o for o in outcomes if o.case_id in above_mde]
    caught = _rate([o.caught for o in claims])
    noise_survives = _rate([o.verdict is Verdict.SURVIVES for o in noise])
    signals_survive = _rate([o.verdict is Verdict.SURVIVES for o in detectable])
    skipped = sum(1 for o in outcomes if o.kind == "defect" and not o.is_claim)
    return (
        Criterion(
            name="defects caught",
            value=caught,
            threshold=MIN_DEFECTS_CAUGHT,
            passed=caught is not None and caught >= MIN_DEFECTS_CAUGHT,
            detail=f"{sum(o.caught for o in claims)} of {len(claims)} defect claims; "
            f"{skipped} defect case(s) without a positive claim left out",
        ),
        Criterion(
            name="noise surviving (false positive rate)",
            value=noise_survives,
            threshold=MAX_NOISE_SURVIVING,
            passed=noise_survives is not None and noise_survives <= MAX_NOISE_SURVIVING,
            detail=f"{sum(o.verdict is Verdict.SURVIVES for o in noise)} of {len(noise)} "
            "IC 0 cases",
        ),
        Criterion(
            name="detectable signals surviving",
            value=signals_survive,
            threshold=MIN_SIGNALS_SURVIVING,
            passed=signals_survive is not None and signals_survive >= MIN_SIGNALS_SURVIVING,
            detail=f"{sum(o.verdict is Verdict.SURVIVES for o in detectable)} of {len(detectable)} "
            f"cases above the minimum detectable Sharpe ({', '.join(sorted(above_mde))})",
        ),
    )


def _confusion(outcomes: Sequence[CaseOutcome]) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {}
    for template in TEMPLATES:
        row = {verdict.value: 0 for verdict in Verdict}
        for outcome in outcomes:
            if outcome.case_id == template.case_id:
                row[outcome.verdict.value] += 1
        table[template.case_id] = row
    return table


def _evaluate_job(job: tuple[CaseTemplate, int, BatteryThresholds]) -> CaseOutcome:
    return evaluate_case(*job)


def run_e1(
    seeds: Sequence[int],
    thresholds: BatteryThresholds | None = None,
    workers: int | None = None,
    progress: Callable[[CaseOutcome], None] | None = None,
    templates: Sequence[CaseTemplate] = TEMPLATES,
) -> E1Report:
    """Run every case on every seed and assess the pre-registered criteria."""
    limits = thresholds or BatteryThresholds()
    jobs = [(template, seed, limits) for template in templates for seed in seeds]
    count = workers if workers is not None else max(1, (os.cpu_count() or 2) - 1)
    outcomes: list[CaseOutcome] = []
    if count == 1:
        for job in jobs:
            outcomes.append(_evaluate_job(job))
            if progress:
                progress(outcomes[-1])
    else:
        with ProcessPoolExecutor(max_workers=count) as pool:
            for outcome in pool.map(_evaluate_job, jobs):
                outcomes.append(outcome)
                if progress:
                    progress(outcome)

    expected = {template.case_id: expected_signal_sharpe(template) for template in SIGNALS[1:]}
    minimum_detectable = minimum_detectable_sharpe(
        business_days(DESIGN_START, DESIGN_END).size, limits
    )
    above = {case for case, sharpe in expected.items() if sharpe >= minimum_detectable}
    return E1Report(
        seeds=tuple(seeds),
        placebo_runs=limits.placebo_runs,
        outcomes=tuple(outcomes),
        confusion=_confusion(outcomes),
        minimum_detectable_sharpe=float(minimum_detectable),
        expected_signal_sharpe=expected,
        criteria=_criteria(outcomes, above),
    )
