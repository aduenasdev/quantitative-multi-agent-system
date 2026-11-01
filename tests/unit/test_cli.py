from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qmas import __version__
from qmas.cli import app
from qmas.config import SOURCE_ROOT
from qmas.ledger import Ledger
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


def test_cli_thesis_validate(tmp_path: Path) -> None:
    assert SOURCE_ROOT is not None
    example = SOURCE_ROOT / "examples" / "theses" / "planted-momentum.yaml"
    result = runner.invoke(app, ["thesis", "validate", str(example)])
    assert result.exit_code == 0
    key, digest = result.output.split()
    assert key == "planted-momentum-v1"
    assert len(digest) == 64
    broken = tmp_path / "broken.yaml"
    broken.write_text("thesis_id: Bad Id\n", encoding="utf-8")
    failed = runner.invoke(app, ["thesis", "validate", str(broken)])
    assert failed.exit_code == 1
    assert "invalid thesis" in failed.output


def test_cli_ledger_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMAS_DATA_DIR", str(tmp_path))
    assert "ledger ok: 0 entries" in runner.invoke(app, ["ledger", "verify"]).output
    Ledger(tmp_path / "ledger.jsonl").append("trial", {"family": "f"})
    assert "ledger ok: 1 entries" in runner.invoke(app, ["ledger", "verify"]).output
    (tmp_path / "ledger.jsonl").write_text('{"sequence": 5}\n', encoding="utf-8")
    result = runner.invoke(app, ["ledger", "verify"])
    assert result.exit_code == 1
    assert "corrupt at line 1" in result.output
