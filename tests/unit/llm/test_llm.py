from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from qmas.config import Settings
from qmas.llm import (
    ConfigurationError,
    LLMClient,
    LLMRequest,
    LLMResponse,
    PromptError,
    PromptRegistry,
    audit_numbers,
    build_client,
    build_provider,
)
from qmas.llm.providers import (
    XAI_BASE_URL,
    AnthropicProvider,
    OpenAICompatibleProvider,
    SimulatedProvider,
)

REQUEST = LLMRequest(system="You explain.", prompt="Explain 1.25.", fallback_text="Draft 1.25.")
NOW = datetime(2026, 11, 1, tzinfo=UTC)


class FakeChat:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.completions = self

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="GPT says 1.25."))],
            usage=SimpleNamespace(
                prompt_tokens=1000,
                completion_tokens=500,
                prompt_tokens_details=SimpleNamespace(cached_tokens=200),
            ),
        )


class FakeMessages:
    def __init__(self, stop_reason: str = "end_turn") -> None:
        self.calls: list[dict[str, Any]] = []
        self.stop_reason = stop_reason

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[
                SimpleNamespace(type="thinking", text=""),
                SimpleNamespace(type="text", text="Claude says 1.25."),
            ],
            usage=SimpleNamespace(input_tokens=800, output_tokens=300, cache_read_input_tokens=700),
        )


class CountingProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="real answer",
            provider=self.name,
            model=self.model,
            input_tokens=1000,
            output_tokens=1000,
        )


def settings(**changes: Any) -> Settings:
    return Settings(**changes)


def test_simulated_provider_returns_the_draft() -> None:
    response = SimulatedProvider().complete(REQUEST)
    assert response.text == "Draft 1.25."
    assert (
        SimulatedProvider()
        .complete(LLMRequest(system="s", prompt="p"))
        .text.startswith("[simulated]")
    )


def test_openai_compatible_provider_maps_the_response() -> None:
    chat = FakeChat()
    provider = OpenAICompatibleProvider(
        "xai", "grok-x", "key", XAI_BASE_URL, client=SimpleNamespace(chat=chat)
    )
    response = provider.complete(REQUEST)
    assert response.text == "GPT says 1.25."
    assert (response.input_tokens, response.output_tokens, response.cached_input_tokens) == (
        1000,
        500,
        200,
    )
    call = chat.calls[0]
    assert call["model"] == "grok-x"
    assert call["messages"][0] == {"role": "system", "content": "You explain."}
    assert call["max_completion_tokens"] == REQUEST.max_output_tokens


def test_anthropic_provider_caches_the_system_prompt() -> None:
    messages = FakeMessages()
    provider = AnthropicProvider(
        "claude-opus-5-5", "key", client=SimpleNamespace(messages=messages)
    )
    response = provider.complete(REQUEST)
    assert response.text == "Claude says 1.25."
    assert response.cached_input_tokens == 700
    call = messages.calls[0]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in call


def test_anthropic_refusal_is_an_error() -> None:
    provider = AnthropicProvider(
        "claude-opus-5-5", "key", client=SimpleNamespace(messages=FakeMessages("refusal"))
    )
    with pytest.raises(RuntimeError, match="declined"):
        provider.complete(REQUEST)


@pytest.mark.parametrize(
    ("changes", "kind"),
    [
        (
            {"llm_provider": "anthropic", "llm_model": "claude-opus-5-5", "anthropic_api_key": "k"},
            AnthropicProvider,
        ),
        (
            {"llm_provider": "openai", "llm_model": "gpt-x", "openai_api_key": "k"},
            OpenAICompatibleProvider,
        ),
        (
            {"llm_provider": "xai", "llm_model": "grok-x", "xai_api_key": "k"},
            OpenAICompatibleProvider,
        ),
        (
            {
                "llm_provider": "openai_compatible",
                "llm_model": "m",
                "llm_api_key": "k",
                "llm_base_url": "https://example.test/v1",
            },
            OpenAICompatibleProvider,
        ),
    ],
)
def test_build_provider(changes: dict[str, Any], kind: type) -> None:
    provider = build_provider(settings(**changes))
    assert isinstance(provider, kind)
    assert provider.model == changes["llm_model"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"llm_provider": "openai", "llm_model": "gpt-x"}, "API key"),
        ({"llm_provider": "anthropic", "anthropic_api_key": "k"}, "QMAS_LLM_MODEL"),
        ({"llm_provider": "openai_compatible", "llm_model": "m", "llm_api_key": "k"}, "BASE_URL"),
    ],
)
def test_build_provider_rejects_incomplete_settings(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        build_provider(settings(**changes))


def test_provider_keys_come_from_their_standard_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    monkeypatch.setenv("QMAS_LLM_PROVIDER", "anthropic")
    loaded = Settings()
    assert loaded.provider_api_key() == "from-env"
    assert "from-env" not in loaded.model_dump_json()


def test_client_caches_and_prices(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    provider = CountingProvider()
    client = LLMClient(provider, tmp_path / "llm.sqlite3", settings(), clock=lambda: NOW)
    first = client.complete(REQUEST)
    second = client.complete(REQUEST)
    assert provider.calls == 1
    assert first.cost_usd == pytest.approx((1000 * 4.0 + 1000 * 20.0) / 1e6)
    assert second.from_cache
    assert second.cost_usd == 0.0
    assert client.month_spent_usd() == pytest.approx(first.cost_usd)
    client.close()


def test_client_without_cache_calls_every_time(tmp_path: Path) -> None:
    provider = CountingProvider()
    client = LLMClient(provider, tmp_path / "llm.sqlite3", settings(llm_cache=False))
    client.complete(REQUEST)
    client.complete(REQUEST)
    assert provider.calls == 2
    client.close()


def test_client_falls_back_to_simulated_when_the_budget_is_reached(tmp_path: Path) -> None:
    provider = CountingProvider()
    tight = settings(llm_run_budget_usd=0.05, llm_cache=False)
    client = LLMClient(provider, tmp_path / "llm.sqlite3", tight, clock=lambda: NOW)
    assert client.complete(REQUEST).text == "real answer"
    fallback = client.complete(REQUEST)
    assert fallback.provider == "simulated"
    assert fallback.text == "Draft 1.25."
    assert provider.calls == 1
    client.close()


def test_monthly_budget_is_shared_between_runs(tmp_path: Path) -> None:
    database = tmp_path / "llm.sqlite3"
    monthly = settings(llm_monthly_budget_usd=0.05, llm_cache=False)
    first = LLMClient(CountingProvider(), database, monthly, clock=lambda: NOW)
    first.complete(REQUEST)
    first.close()
    second_provider = CountingProvider()
    second = LLMClient(second_provider, database, monthly, clock=lambda: NOW)
    assert second.complete(REQUEST).provider == "simulated"
    assert second_provider.calls == 0
    second.close()


def test_simulated_client_warns_and_build_client_uses_the_data_dir(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="qmas.llm"):
        client = build_client(settings(data_dir=tmp_path))
    assert "simulated mode" in caplog.text
    assert client.complete(REQUEST).text == "Draft 1.25."
    assert (tmp_path / "llm.sqlite3").is_file()
    client.close()


def test_prompt_registry_checks_hashes(tmp_path: Path) -> None:
    (tmp_path / "greeting.md").write_text("Hello $name.\n", encoding="utf-8")
    registry = PromptRegistry(tmp_path)
    with pytest.raises(PromptError, match="not locked"):
        registry.text("greeting")
    hashes = registry.lock()
    assert registry.render("greeting", name="Ada") == "Hello Ada.\n"
    assert registry.hash("greeting") == hashes["greeting"]
    (tmp_path / "greeting.md").write_text("Hello $name!\n", encoding="utf-8")
    with pytest.raises(PromptError, match="changed"):
        PromptRegistry(tmp_path).text("greeting")
    with pytest.raises(PromptError, match="unknown"):
        registry.text("missing")


def test_packaged_prompts_match_their_lock() -> None:
    registry = PromptRegistry()
    for prompt_id in ("reporter_system", "reporter_memo"):
        assert len(registry.hash(prompt_id)) == 64


@pytest.mark.parametrize(
    ("text", "allowed", "ok", "unknown"),
    [
        ("Sharpe 1.25 after 200 shuffles.", [1.2512, 200], True, ()),
        ("Retention 85% of the claim.", [0.8512], True, ()),
        ("Sharpe 1.3 is wrong.", [1.2412], False, ("1.3",)),
        ("A10 and P7 in 2021 are not figures.", [], True, ()),
        ("A loss of -0.42 here.", [-0.4249], True, ()),
        ("Invented 3.14 and 7%.", [0.5], False, ("3.14", "7%")),
    ],
)
def test_number_audit(text: str, allowed: list[float], ok: bool, unknown: tuple[str, ...]) -> None:
    result = audit_numbers(text, allowed)
    assert result.ok is ok
    assert result.unknown == unknown
