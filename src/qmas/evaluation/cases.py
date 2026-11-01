"""E1 case library: ten planted defects and five planted signal strengths.

Each case is a market (a ``MarketConfig`` change) plus the strategy an author would claim.
Defects that live in the author's implementation (look-ahead, survivor universe, ignored costs,
selection among many trials, time-zone error) are set through strategy switches that the battery
never reads: it can only re-run the strategy with switches of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from qmas.backtest import StrategySpec, run_backtest
from qmas.market import MarketConfig, generate_market
from qmas.red_team import AttackContext, BatteryThresholds, TrialSet

CALIBRATION_SEEDS: tuple[int, ...] = (1000, 1001, 1002, 1003, 1004)
JUDGEMENT_SEEDS: tuple[int, ...] = (2000, 2001, 2002, 2003, 2004)
DESIGN_START, DESIGN_END = date(2016, 1, 4), date(2021, 12, 31)
SELECTION_TRIALS = 200
PLANTED_LEVELS: tuple[float, ...] = (0.0, 0.01, 0.02, 0.04, 0.08)

CaseKind = Literal["defect", "signal"]


@dataclass(frozen=True)
class CaseTemplate:
    """A case before a seed is chosen."""

    case_id: str
    kind: CaseKind
    description: str
    market: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    expected_attacks: tuple[str, ...] = ()
    selection_trials: int = 0
    planted_ic: float | None = None


def _daily(**changes: Any) -> dict[str, Any]:
    return {"horizon_days": 1, "rebalance_every_days": 1, **changes}


DEFECTS: tuple[CaseTemplate, ...] = (
    CaseTemplate(
        "P1",
        "defect",
        "signal uses the next day's return",
        strategy=_daily(signal="future_return"),
        expected_attacks=("A1",),
    ),
    CaseTemplate(
        "P2",
        "defect",
        "universe is today's survivors",
        market={"delisting_rate_annual": 0.03, "distress_decline": -0.7},
        strategy={
            "signal": "trailing_return",
            "signal_parameters": {"invert": True},
            "universe": "survivors",
        },
        expected_attacks=("A2",),
    ),
    CaseTemplate(
        "P3",
        "defect",
        "high-turnover edge that only exists before costs",
        market={"reversal_strength": 0.05},
        strategy=_daily(signal="short_term_reversal", cost_bps=0.0),
        expected_attacks=("A3",),
    ),
    CaseTemplate(
        "P4",
        "defect",
        "best of 200 noise signals in the design window",
        expected_attacks=("A4", "A5"),
        selection_trials=SELECTION_TRIALS,
    ),
    CaseTemplate(
        "P5",
        "defect",
        "the whole result comes from one name's jump",
        market={"jump_size": 3.0},
        strategy={"quantile": 0.025},
        expected_attacks=("A9",),
    ),
    CaseTemplate(
        "P6",
        "defect",
        "New York clock times read as UTC",
        strategy=_daily(
            signal="event_surprise", signal_parameters={"timestamps_as_utc": True}, quantile=0.5
        ),
        expected_attacks=("A1",),
    ),
    CaseTemplate(
        "P7",
        "defect",
        "one wrong price in the primary source",
        market={"price_error_size": 2.0},
        strategy={"quantile": 0.025},
        expected_attacks=("A13",),
    ),
    CaseTemplate(
        "P8",
        "defect",
        "works only in 2020-2021",
        market={"planted_ic": 0.08, "signal_active_years": (2020, 2021)},
        expected_attacks=("A7",),
    ),
    CaseTemplate(
        "P9",
        "defect",
        "works only on one rebalancing day",
        market={"planted_ic": 0.08, "signal_front_loaded": True},
        expected_attacks=("A8",),
    ),
    CaseTemplate(
        "P10",
        "defect",
        "market beta disguised as alpha",
        market={"market_drift_annual": 0.20, "market_vol_annual": 0.12},
        strategy={"signal": "beta_exposure", "portfolio": "long_only"},
        expected_attacks=("A6",),
    ),
)

SIGNALS: tuple[CaseTemplate, ...] = tuple(
    CaseTemplate(
        f"IC{level:.2f}",
        "signal",
        f"planted characteristic with rank IC {level:.2f}",
        market={"planted_ic": level},
        planted_ic=level,
    )
    for level in PLANTED_LEVELS
)

TEMPLATES: tuple[CaseTemplate, ...] = DEFECTS + SIGNALS


def claimed_strategy(template: CaseTemplate) -> StrategySpec:
    """Return the strategy the author of the case would claim."""
    base = StrategySpec(
        signal="planted_characteristic", start=DESIGN_START, end=DESIGN_END, cost_bps=10.0
    )
    return replace(base, **template.strategy)


def market_config(template: CaseTemplate) -> MarketConfig:
    """Return the market of the case."""
    return replace(MarketConfig(), **template.market)


def build_context(
    template: CaseTemplate, seed: int, thresholds: BatteryThresholds
) -> AttackContext:
    """Generate the market, run the author's claim and return the context to attack."""
    market = generate_market(market_config(template), seed)
    strategy = claimed_strategy(template)
    if not template.selection_trials:
        return AttackContext(market, strategy, TrialSet(), thresholds, seed)
    # The author tried many candidates and reports the best one; every trial is in the ledger.
    candidates = [
        replace(strategy, signal="random_characteristic", signal_parameters={"seed": index})
        for index in range(template.selection_trials)
    ]
    results = [run_backtest(market, candidate) for candidate in candidates]
    best = int(np.argmax([result.sharpe() for result in results]))
    trials = TrialSet(
        n_trials=template.selection_trials,
        returns=np.column_stack([result.net_returns for result in results]),
    )
    return AttackContext(market, candidates[best], trials, thresholds, seed, claimed=results[best])
