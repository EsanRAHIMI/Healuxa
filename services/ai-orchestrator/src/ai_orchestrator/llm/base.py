"""LLMProvider port: the only seam between the assistant and a model vendor (anti-corruption layer).

Messages use the Anthropic Messages shape (role + content blocks) because that is the provider in
use; ``ModelStep.assistant_content`` is opaque to the engine and is appended back unchanged so
provider-specific blocks (thinking, fallback) survive the tool loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMUnavailable(Exception):
    """No model is configured (e.g. ANTHROPIC_API_KEY unset). Surfaces as a clear 503."""


class LLMError(Exception):
    """The provider call failed. ``code`` is one of: rate_limited | unavailable | invalid."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: Any


@dataclass
class ModelStep:
    assistant_content: Any
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    @property
    def available(self) -> bool: ...

    def stream_step(
        self, *, system: list[dict[str, Any]], messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[TextDelta | ModelStep]:
        """Yield TextDelta chunks, then exactly one ModelStep."""
        ...
