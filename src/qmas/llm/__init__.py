"""LLM layer: providers, exact cache, spending caps, prompt registry and number audit."""

from qmas.llm.client import ConfigurationError, LLMClient, build_client, build_provider
from qmas.llm.number_audit import AuditResult, audit_numbers
from qmas.llm.prompts import PromptError, PromptRegistry
from qmas.llm.types import LLMRequest, LLMResponse, Provider

__all__ = [
    "AuditResult",
    "ConfigurationError",
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "PromptError",
    "PromptRegistry",
    "Provider",
    "audit_numbers",
    "build_client",
    "build_provider",
]
