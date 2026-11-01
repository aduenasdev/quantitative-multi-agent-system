"""The LLM client every agent uses: exact cache, spending caps and a simulated fallback.

Rule: RULE-BUDGET-01. Every call is priced before it is recorded; a call that would exceed the
per-run or the monthly cap is not sent and the client answers in simulated mode instead.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from qmas.canonical import canonical_json, sha256_hex
from qmas.config import Settings
from qmas.llm.providers import (
    XAI_BASE_URL,
    AnthropicProvider,
    OpenAICompatibleProvider,
    SimulatedProvider,
)
from qmas.llm.types import LLMRequest, LLMResponse, Provider

LOGGER = logging.getLogger("qmas.llm")
TOKENS_PER_MILLION = 1_000_000


class ConfigurationError(ValueError):
    """Raised when the LLM settings are incomplete."""


def build_provider(settings: Settings) -> Provider:
    """Return the provider named in the settings; ``simulated`` needs nothing."""
    kind = settings.llm_provider
    if kind == "simulated":
        return SimulatedProvider()
    key = settings.provider_api_key()
    if not key:
        raise ConfigurationError(f"provider {kind!r} needs its API key (see .env.example)")
    if not settings.llm_model:
        raise ConfigurationError(f"provider {kind!r} needs QMAS_LLM_MODEL")
    timeout = settings.llm_timeout_seconds
    if kind == "anthropic":
        return AnthropicProvider(settings.llm_model, key, timeout)
    if kind == "openai":
        return OpenAICompatibleProvider("openai", settings.llm_model, key, None, timeout)
    if kind == "xai":
        base_url = settings.llm_base_url or XAI_BASE_URL
        return OpenAICompatibleProvider("xai", settings.llm_model, key, base_url, timeout)
    if not settings.llm_base_url:
        raise ConfigurationError("provider 'openai_compatible' needs QMAS_LLM_BASE_URL")
    return OpenAICompatibleProvider(
        "openai_compatible", settings.llm_model, key, settings.llm_base_url, timeout
    )


class LLMClient:
    """Cache, budget and fallback around one provider."""

    def __init__(
        self,
        provider: Provider,
        database: Path,
        settings: Settings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """Open (and create) the SQLite database that holds the cache and the spending."""
        self.provider = provider
        self.settings = settings
        self._clock = clock
        self._fallback = SimulatedProvider()
        self.run_spent_usd = 0.0
        database.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(database)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response TEXT)")
        self._db.execute("CREATE TABLE IF NOT EXISTS spend (month TEXT, cost_usd REAL)")
        if provider.name == "simulated":
            LOGGER.warning("LLM in simulated mode: answers are deterministic drafts, no API calls")

    def close(self) -> None:
        """Close the database."""
        self._db.close()

    def cost(self, response: LLMResponse) -> float:
        """Return the price of a response with the configured per-token prices."""
        return (
            response.input_tokens * self.settings.llm_input_usd_per_mtok
            + response.output_tokens * self.settings.llm_output_usd_per_mtok
        ) / TOKENS_PER_MILLION

    def month_spent_usd(self) -> float:
        """Return what the current calendar month has cost so far."""
        month = self._clock().strftime("%Y-%m")
        row = self._db.execute(
            "SELECT SUM(cost_usd) FROM spend WHERE month = ?", (month,)
        ).fetchone()
        return float(row[0] or 0.0)

    def _within_budget(self, request: LLMRequest) -> bool:
        worst_case = (
            request.max_output_tokens * self.settings.llm_output_usd_per_mtok / TOKENS_PER_MILLION
        )
        run_ok = self.run_spent_usd + worst_case <= self.settings.llm_run_budget_usd
        month_ok = self.month_spent_usd() + worst_case <= self.settings.llm_monthly_budget_usd
        return run_ok and month_ok

    def _key(self, request: LLMRequest) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "provider": self.provider.name,
                    "model": self.provider.model,
                    **request.model_dump(),
                }
            )
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Answer from the cache, else from the provider within budget, else in simulated mode."""
        key = self._key(request)
        if self.settings.llm_cache:
            row = self._db.execute("SELECT response FROM cache WHERE key = ?", (key,)).fetchone()
            if row:
                cached = LLMResponse.model_validate_json(row[0])
                return cached.model_copy(update={"from_cache": True, "cost_usd": 0.0})
        if self.provider.name != "simulated" and not self._within_budget(request):
            LOGGER.warning("LLM budget reached: answering in simulated mode (RULE-BUDGET-01)")
            return self._fallback.complete(request)
        response = self.provider.complete(request)
        response = response.model_copy(update={"cost_usd": self.cost(response)})
        self.run_spent_usd += response.cost_usd
        with self._db:
            self._db.execute(
                "INSERT INTO spend VALUES (?, ?)",
                (self._clock().strftime("%Y-%m"), response.cost_usd),
            )
            if self.settings.llm_cache and self.provider.name != "simulated":
                self._db.execute(
                    "INSERT OR IGNORE INTO cache VALUES (?, ?)", (key, response.model_dump_json())
                )
        return response


def build_client(settings: Settings) -> LLMClient:
    """Return the client configured by ``settings``, storing its state in the data directory."""
    return LLMClient(build_provider(settings), settings.data_dir / "llm.sqlite3", settings)
