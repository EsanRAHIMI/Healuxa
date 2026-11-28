from __future__ import annotations

from ai_orchestrator.config import settings
from ai_orchestrator.llm.base import LLMProvider

_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Process-wide provider selected by LLM_PROVIDER. Tests replace it with ``set_llm``."""
    global _provider
    if _provider is None:
        if settings.llm_provider == "fake":
            from ai_orchestrator.llm.fake import FakeProvider

            _provider = FakeProvider()
        else:
            from ai_orchestrator.llm.anthropic_provider import AnthropicProvider

            _provider = AnthropicProvider()
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    global _provider
    _provider = provider
