"""Provider-neutral request and response of one LLM call."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMRequest(BaseModel):
    """One completion request: a stable system prompt and a user prompt."""

    model_config = ConfigDict(frozen=True)

    system: str
    prompt: str
    max_output_tokens: int = Field(default=2000, ge=1)
    fallback_text: str = Field(
        default="", description="What the simulated provider answers (a deterministic draft)."
    )


class LLMResponse(BaseModel):
    """Text and accounting of one completion."""

    model_config = ConfigDict(frozen=True)

    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cost_usd: float = 0.0
    from_cache: bool = False


class Provider(Protocol):
    """Anything that turns a request into a response."""

    name: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the completion of ``request``."""
        ...
