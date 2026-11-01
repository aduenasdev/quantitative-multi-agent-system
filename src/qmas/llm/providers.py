"""LLM providers: simulated, OpenAI, xAI (Grok) and any OpenAI-compatible endpoint, and Anthropic.

OpenAI, xAI, OpenRouter and OpenCode Zen speak the OpenAI chat-completions protocol, so one provider
class covers them with a different ``base_url``. Anthropic uses its own SDK, with the system prompt
marked for prompt caching.
"""

from __future__ import annotations

from typing import Any

import anthropic
import openai

from qmas.llm.types import LLMRequest, LLMResponse

XAI_BASE_URL = "https://api.x.ai/v1"


class SimulatedProvider:
    """Deterministic provider used without keys and in tests: answers with the request's draft."""

    name = "simulated"
    model = "simulated"

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the fallback draft of the request (or a fixed notice when there is none)."""
        text = request.fallback_text or "[simulated] no draft was provided."
        return LLMResponse(text=text, provider=self.name, model=self.model)


class OpenAICompatibleProvider:
    """Chat-completions provider (OpenAI, xAI, OpenRouter, OpenCode Zen...)."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        client: Any | None = None,
    ) -> None:
        """Create the provider; ``client`` replaces the SDK client (tests)."""
        self.name = name
        self.model = model
        self._client: Any = client or openai.OpenAI(
            api_key=api_key, base_url=base_url or None, timeout=timeout_seconds
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send one chat-completions request."""
        response = self._client.chat.completions.create(
            model=self.model,
            max_completion_tokens=request.max_output_tokens,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        )
        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None)
        return LLMResponse(
            text=response.choices[0].message.content or "",
            provider=self.name,
            model=self.model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            cached_input_tokens=int(getattr(details, "cached_tokens", 0) or 0),
        )


class AnthropicProvider:
    """Claude through the official Anthropic SDK, with the system prompt cached."""

    name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        timeout_seconds: float = 60.0,
        client: Any | None = None,
    ) -> None:
        """Create the provider; ``client`` replaces the SDK client (tests)."""
        self.model = model
        self._client: Any = client or anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send one Messages API request and refuse to return a declined answer as text."""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=request.max_output_tokens,
            system=[
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": request.prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("the model declined the request")
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=int(usage.input_tokens or 0),
            output_tokens=int(usage.output_tokens or 0),
            cached_input_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        )
