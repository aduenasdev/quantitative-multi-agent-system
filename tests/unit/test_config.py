from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from qmas.config import DEFAULT_SEED, SOURCE_ROOT, Settings, default_data_dir, get_settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.log_level == "INFO"
    assert settings.seed == DEFAULT_SEED
    assert settings.data_dir == default_data_dir()


def test_default_data_dir_is_inside_the_checkout() -> None:
    assert SOURCE_ROOT is not None
    assert default_data_dir() == SOURCE_ROOT / "data"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QMAS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("QMAS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("QMAS_SEED", "7")
    settings = Settings()
    assert settings.data_dir == tmp_path
    assert settings.log_level == "DEBUG"
    assert settings.seed == 7


def test_settings_reads_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("QMAS_SEED=11\n", encoding="utf-8")
    assert Settings(_env_file=env_file).seed == 11  # type: ignore[call-arg]


def test_settings_empty_values_use_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMAS_DATA_DIR", "")
    assert Settings().data_dir == default_data_dir()


def test_env_example_lists_every_setting() -> None:
    assert SOURCE_ROOT is not None
    example = (SOURCE_ROOT / ".env.example").read_text(encoding="utf-8")
    for name, field in Settings.model_fields.items():
        variable = (
            field.validation_alias.choices[0]  # type: ignore[union-attr]
            if field.validation_alias is not None
            else f"QMAS_{name.upper()}"
        )
        assert f"{variable}=" in example


def test_settings_rejects_invalid_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QMAS_LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
