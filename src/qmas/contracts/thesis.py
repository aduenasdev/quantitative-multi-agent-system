"""Thesis contract: the complete, pre-registered description of a trading hypothesis.

Rule: RULE-PREREG-01. A thesis is frozen once registered; any change is a new ``version``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from qmas.canonical import canonical_json, sha256_hex

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ParameterValue = int | float | str | bool


class FrozenModel(BaseModel):
    """Immutable model that rejects unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Window(FrozenModel):
    """Inclusive date window."""

    start: date
    end: date

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("window end must be after its start")
        return self


class DataSpec(FrozenModel):
    """Where the market data comes from."""

    source: Literal["synthetic"] = Field(description="Data source; the MVP is synthetic only.")
    seed: int = Field(ge=0, description="Seed of the synthetic market.")
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)


class SignalSpec(FrozenModel):
    """A signal chosen by name from the signal registry; never code."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)


class Thresholds(FrozenModel):
    """Pre-registered pass thresholds."""

    min_deflated_sharpe: float = Field(default=0.95, gt=0, lt=1)
    max_overfitting_probability: float = Field(default=0.5, gt=0, lt=1)
    max_p_value: float = Field(default=0.05, gt=0, lt=1)


class Thesis(FrozenModel):
    """A trading hypothesis, complete enough to be tested without further choices."""

    thesis_id: str = Field(pattern=SLUG_PATTERN)
    version: int = Field(default=1, ge=1)
    family: str = Field(pattern=SLUG_PATTERN)
    title: str = Field(min_length=3, max_length=120)
    hypothesis: str = Field(min_length=10)
    data: DataSpec
    signal: SignalSpec
    horizon_days: int = Field(ge=1, le=252)
    rebalance_every_days: int = Field(ge=1, le=252)
    design_window: Window
    holdout_window: Window
    cost_bps: float = Field(ge=0, le=500, description="One-way cost per unit of turnover.")
    thresholds: Thresholds = Field(default_factory=Thresholds)

    @model_validator(mode="after")
    def _check_windows(self) -> Self:
        if self.holdout_window.start <= self.design_window.end:
            raise ValueError("the holdout window must start after the design window ends")
        return self

    @property
    def key(self) -> str:
        """Return ``<thesis_id>-v<version>``, the identifier of this exact version."""
        return f"{self.thesis_id}-v{self.version}"

    def content_hash(self) -> str:
        """Return the SHA-256 of the canonical JSON of the thesis."""
        return sha256_hex(canonical_json(self.model_dump(mode="json")))


def load_thesis(path: Path) -> Thesis:
    """Read and validate a thesis from a YAML file."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path}: a thesis must be a YAML mapping")
    return Thesis.model_validate(document)
