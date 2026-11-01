"""Typed application settings, loaded from the environment and an optional ``.env`` file.

Every environment-specific value lives here; nothing else in the package reads ``os.environ``.
Variables use the ``QMAS_`` prefix and are documented in ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["simulated", "openai", "anthropic", "xai", "openai_compatible"]

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
        populate_by_name=True,
    )

    data_dir: Path = Field(
        default_factory=default_data_dir,
        description="Directory for the ledger, checkpoints, caches and reports.",
    )
    log_level: LogLevel = Field(default="INFO", description="Standard logging level.")
    seed: int = Field(default=DEFAULT_SEED, description="Base random seed for reproducible runs.")

    # LLM layer (spec 0009). Without a provider the system runs in simulated mode.
    llm_provider: LLMProvider = Field(default="simulated", description="Who answers LLM calls.")
    llm_model: str = Field(default="", description="Model id of the provider.")
    llm_base_url: str = Field(default="", description="Endpoint for openai_compatible providers.")
    llm_api_key: SecretStr | None = Field(default=None, description="Key of openai_compatible.")
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    xai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("XAI_API_KEY")
    )
    llm_max_output_tokens: int = Field(default=2000, ge=1)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_cache: bool = True
    llm_input_usd_per_mtok: float = Field(default=4.0, ge=0)
    llm_output_usd_per_mtok: float = Field(default=20.0, ge=0)
    llm_run_budget_usd: float = Field(default=0.50, ge=0)
    llm_monthly_budget_usd: float = Field(default=20.0, ge=0)

    def provider_api_key(self) -> str | None:
        """Return the API key of the configured provider, if any."""
        secret = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "xai": self.xai_api_key,
            "openai_compatible": self.llm_api_key,
        }.get(self.llm_provider)
        return secret.get_secret_value() if secret else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""
    return Settings()
