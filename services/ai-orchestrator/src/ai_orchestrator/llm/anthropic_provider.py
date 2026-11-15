"""Claude via the official Anthropic Python SDK (streaming Messages API with client-side tools)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from ai_orchestrator.config import settings
from ai_orchestrator.llm.base import LLMError, LLMUnavailable, ModelStep, TextDelta, ToolCall

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self._client: anthropic.AsyncAnthropic | None = None
        if settings.anthropic_api_key:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.anthropic_timeout_seconds,
                max_retries=settings.anthropic_max_retries,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    def _open_stream(self, *, system: list[dict[str, Any]], messages: list[dict[str, Any]], tools: list[dict[str, Any]]):
        assert self._client is not None
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": settings.anthropic_max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
            # Thinking is adaptive by default on current models; effort is the depth/latency control.
            "output_config": {"effort": settings.anthropic_effort},
        }
        if settings.anthropic_refusal_fallback:
            # On a safety decline the API re-runs the request on a fallback model inside the same call.
            return self._client.beta.messages.stream(**params, betas=[FALLBACK_BETA], fallbacks="default")
        return self._client.messages.stream(**params)

    async def stream_step(
        self, *, system: list[dict[str, Any]], messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[TextDelta | ModelStep]:
        if self._client is None:
            raise LLMUnavailable()
        try:
            async with self._open_stream(system=system, messages=messages, tools=tools) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield TextDelta(event.text)
                message = await stream.get_final_message()
        except anthropic.RateLimitError:
            raise LLMError("rate_limited") from None
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            # A bad key is a deployment fault: report the assistant as unavailable, never leak details.
            logger.error("anthropic rejected the configured credentials")
            raise LLMUnavailable() from None
        except anthropic.BadRequestError as exc:
            logger.error("anthropic rejected the request (status %s, request %s)", exc.status_code, exc.request_id)
            raise LLMError("invalid") from None
        except anthropic.APIStatusError as exc:
            logger.warning("anthropic error status %s (request %s)", exc.status_code, exc.request_id)
            raise LLMError("unavailable") from None
        except anthropic.APIConnectionError:  # includes APITimeoutError
            raise LLMError("unavailable") from None

        text = "".join(block.text for block in message.content if block.type == "text")
        calls = [ToolCall(id=block.id, name=block.name, input=block.input) for block in message.content if block.type == "tool_use"]
        yield ModelStep(
            assistant_content=message.content,
            text=text,
            tool_calls=calls,
            stop_reason=message.stop_reason,
            input_tokens=message.usage.input_tokens or 0,
            output_tokens=message.usage.output_tokens or 0,
            model=message.model,
        )
