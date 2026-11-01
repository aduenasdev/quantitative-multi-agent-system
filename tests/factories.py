"""Builders of valid domain objects for tests."""

from __future__ import annotations

from datetime import date
from typing import Any

from qmas.contracts.thesis import Thesis


def thesis_document(**overrides: Any) -> dict[str, Any]:
    """Return a valid thesis as a plain mapping, with optional top-level overrides."""
    document: dict[str, Any] = {
        "thesis_id": "test-thesis",
        "version": 1,
        "family": "test-family",
        "title": "A test thesis",
        "hypothesis": "A planted signal predicts returns.",
        "data": {"source": "synthetic", "seed": 1, "parameters": {"n_assets": 50}},
        "signal": {"name": "planted_characteristic", "parameters": {}},
        "horizon_days": 21,
        "rebalance_every_days": 21,
        "design_window": {"start": date(2016, 1, 4), "end": date(2019, 12, 31)},
        "holdout_window": {"start": date(2020, 1, 2), "end": date(2020, 12, 31)},
        "cost_bps": 10.0,
    }
    document.update(overrides)
    return document


def make_thesis(**overrides: Any) -> Thesis:
    """Return a valid ``Thesis`` with optional top-level overrides."""
    return Thesis.model_validate(thesis_document(**overrides))
