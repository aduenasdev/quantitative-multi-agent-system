"""Shared fixtures: isolate every test from the developer's environment and ``.env``."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from qmas.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove ``QMAS_*`` variables, ignore ``.env`` and reset the settings cache."""
    for name in list(os.environ):
        if name.startswith("QMAS_"):
            monkeypatch.delenv(name)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
