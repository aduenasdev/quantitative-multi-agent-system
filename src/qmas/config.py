"""Typed application settings, loaded from the environment and an optional ``.env`` file.

Every environment-specific value lives here; nothing else in the package reads ``os.environ``.
Variables use the ``QMAS_`` prefix and are documented in ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DEFAULT_SEED = 20260929


def find_source_root() -> Path | None:
    """Return the repository root when running from a source checkout, otherwise ``None``.

    A source checkout is recognised by ``pyproject.toml`` two levels above the package
    (``src`` layout).
    """
    candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "pyproject.toml").is_file() else None


SOURCE_ROOT = find_source_root()


def default_data_dir() -> Path:
    """Return ``<repo>/data`` in a source checkout, or ``~/.qmas/data`` for an installed package."""
    if SOURCE_ROOT is not None:
        return SOURCE_ROOT / "data"
    return Path.home() / ".qmas" / "data"


class Settings(BaseSettings):
    """Runtime configuration of the system."""

    model_config = SettingsConfigDict(
        env_prefix="QMAS_",
        env_file=(SOURCE_ROOT / ".env") if SOURCE_ROOT is not None else None,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    data_dir: Path = Field(
        default_factory=default_data_dir,
        description="Directory for the ledger, checkpoints, caches and reports.",
    )
    log_level: LogLevel = Field(default="INFO", description="Standard logging level.")
    seed: int = Field(default=DEFAULT_SEED, description="Base random seed for reproducible runs.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""
    return Settings()
