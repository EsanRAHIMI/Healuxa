"""The Anthropic adapter against the real SDK, with the HTTP layer mocked (no network, no key needed).

Verifies the request the SDK actually sends (model, tools, effort, cache breakpoint, fallback beta)
and that a streamed tool_use response is parsed into a ModelStep. It does NOT prove the live API
accepts the request — that needs ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json

import anthropic
import httpx2
import pytest

from ai_orchestrator.config import settings
from ai_orchestrator.domain.prompt import build_system
from ai_orchestrator.domain.tools import TOOL_DEFINITIONS
from ai_orchestrator.llm.anthropic_provider import AnthropicProvider
from ai_orchestrator.llm.base import LLMError, LLMUnavailable, ModelStep, TextDelta


def _sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


STREAM = [
    ("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 12, "output_tokens": 1}}}),
    ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Let me check."}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
    ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "search_services", "input": {}}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"category\": \"dental\"}"}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 1}),
    ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 20}}),
    ("message_stop", {"type": "message_stop"}),
]


def _provider(handler, monkeypatch: pytest.MonkeyPatch, *, fallback: bool = True) -> AnthropicProvider:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-not-a-real-key")
    monkeypatch.setattr(settings, "anthropic_refusal_fallback", fallback)
    provider = AnthropicProvider()
    provider._client = anthropic.AsyncAnthropic(
        api_key="sk-ant-test-not-a-real-key", max_retries=0, http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    )
    return provider


async def _run(provider: AnthropicProvider) -> list:
    from datetime import date

    out = []
    async for item in provider.stream_step(system=build_system("en", date(2030, 1, 1)), messages=[{"role": "user", "content": "dental"}], tools=TOOL_DEFINITIONS):
        out.append(item)
    return out


async def test_request_shape_and_streamed_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(STREAM))

    items = await _run(_provider(handler, monkeypatch))
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5" and body["stream"] is True
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]
    assert "thinking" not in body and "temperature" not in body and "tool_choice" not in body
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert [t["name"] for t in body["tools"]] == [t["name"] for t in TOOL_DEFINITIONS]
    assert all(t["strict"] is True and t["input_schema"]["additionalProperties"] is False for t in body["tools"])
    assert [i.text for i in items if isinstance(i, TextDelta)] == ["Let me check."]
    step = items[-1]
    assert isinstance(step, ModelStep) and step.stop_reason == "tool_use"
    assert [(c.name, c.input) for c in step.tool_calls] == [("search_services", {"category": "dental"})]
    assert step.input_tokens == 12 and step.output_tokens == 20


async def test_without_fallback_uses_the_ga_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(STREAM))

    await _run(_provider(handler, monkeypatch, fallback=False))
    body = json.loads(seen[0].content)
    assert "fallbacks" not in body and "server-side-fallback" not in seen[0].headers.get("anthropic-beta", "")


@pytest.mark.parametrize(("status", "expected"), [(429, LLMError), (529, LLMError), (500, LLMError), (400, LLMError), (401, LLMUnavailable)])
async def test_provider_errors_are_mapped(monkeypatch: pytest.MonkeyPatch, status: int, expected: type) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"type": "error", "error": {"type": "x", "message": "secret detail"}})

    with pytest.raises(expected):
        await _run(_provider(handler, monkeypatch))
