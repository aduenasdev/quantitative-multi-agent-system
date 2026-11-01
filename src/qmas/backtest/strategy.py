"""Strategy specification and its construction from a thesis."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from types import MappingProxyType
from typing import Literal

from qmas.contracts.thesis import Thesis
from qmas.market import MarketConfig, SyntheticMarket, generate_market
from qmas.market.signals import Parameters

Window = Literal["design", "holdout"]


@dataclass(frozen=True)
class StrategySpec:
    """Everything the engine needs; each field is a switch the red team can flip."""

    signal: str
    start: date
    end: date
    signal_parameters: Parameters = field(default_factory=lambda: MappingProxyType({}))
    horizon_days: int = 21
    rebalance_every_days: int = 21
    offset: int = 0
    portfolio: Literal["long_short", "long_only"] = "long_short"
    quantile: float = 0.2
    universe: Literal["point_in_time", "survivors"] = "point_in_time"
    execution_delay: int = 0
    price_source: Literal["primary", "secondary"] = "primary"
    cost_model: Literal["flat", "per_name"] = "flat"
    cost_bps: float = 0.0
    excluded_assets: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        """Validate the switches."""
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.horizon_days < 1 or self.rebalance_every_days < 1:
            raise ValueError("horizon_days and rebalance_every_days must be positive")
        if self.horizon_days % self.rebalance_every_days:
            raise ValueError("horizon_days must be a multiple of rebalance_every_days")
        if not 0 <= self.offset < self.rebalance_every_days:
            raise ValueError("offset must be in [0, rebalance_every_days)")
        if not 0 < self.quantile <= 0.5:
            raise ValueError("quantile must be in (0, 0.5]")
        if self.execution_delay < 0 or self.cost_bps < 0:
            raise ValueError("execution_delay and cost_bps must be non-negative")

    @property
    def tranches(self) -> int:
        """Return the number of overlapping tranches held at the same time."""
        return self.horizon_days // self.rebalance_every_days


def strategy_from_thesis(thesis: Thesis, window: Window = "design") -> StrategySpec:
    """Return the strategy a thesis describes, on its design or holdout window."""
    span = thesis.design_window if window == "design" else thesis.holdout_window
    return StrategySpec(
        signal=thesis.signal.name,
        signal_parameters=MappingProxyType(dict(thesis.signal.parameters)),
        start=span.start,
        end=span.end,
        horizon_days=thesis.horizon_days,
        rebalance_every_days=thesis.rebalance_every_days,
        portfolio=thesis.portfolio.kind,
        quantile=thesis.portfolio.quantile,
        cost_bps=thesis.cost_bps,
    )


MARKET_PARAMETERS = frozenset(
    item.name for item in fields(MarketConfig) if item.type in {"int", "float", "bool"}
)


def market_from_thesis(thesis: Thesis) -> SyntheticMarket:
    """Generate the synthetic market named by ``thesis.data``; unknown parameters are rejected."""
    unknown = set(thesis.data.parameters) - MARKET_PARAMETERS
    if unknown:
        raise ValueError(f"unknown market parameters: {', '.join(sorted(unknown))}")
    config = MarketConfig(**thesis.data.parameters)  # type: ignore[arg-type]
    return generate_market(config, thesis.data.seed)
