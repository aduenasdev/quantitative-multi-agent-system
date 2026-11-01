from __future__ import annotations

import json
import logging

import pytest
from typer.testing import CliRunner

from qmas import __version__
from qmas.cli import app
from qmas.logging_setup import HANDLER_NAME, LOGGER_NAME, configure_logging

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"qmas {__version__}"


def test_cli_without_arguments_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_cli_config_show(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMAS_SEED", "42")
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["seed"] == 42
    assert payload["log_level"] == "INFO"


def test_configure_logging_is_idempotent() -> None:
    first = configure_logging("INFO")
    second = configure_logging("DEBUG")
    assert first is second is logging.getLogger(LOGGER_NAME)
    assert [h.get_name() for h in second.handlers].count(HANDLER_NAME) == 1
    assert second.level == logging.DEBUG
