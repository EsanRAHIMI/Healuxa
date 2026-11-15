"""One assistant turn: code guardrails → bounded tool loop → output checks → cards.

Yields ("delta" | "status" | "replace", payload) events for streaming and finally ("result", TurnResult).
Message text is never logged here; only tool names, counts and outcomes are.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from prometheus_client import Counter

from ai_orchestrator.config import settings
from ai_orchestrator.domain import guardrails
from ai_orchestrator.domain.messages import message
from ai_orchestrator.domain.prompt import build_system
from ai_orchestrator.domain.tools import (
    BOOKABLE_STEP_CODES,
    HANDOFF_CARD,
    TOOL_DEFINITIONS,
    TurnContext,
    build_card,
    case_card,
    execute_tool,
)
from ai_orchestrator.llm.base import LLMError, LLMProvider, LLMUnavailable, ModelStep, TextDelta

logger = logging.getLogger(__name__)

TURNS = Counter("healuxa_ai_turns_total", "Assistant turns by outcome", ["outcome"])
TOOL_CALLS = Counter("healuxa_ai_tool_calls_total", "Assistant tool calls", ["tool", "outcome"])
REJECTED_CARDS = Counter("healuxa_ai_rejected_cards_total", "Cards dropped because the id was not returned by a tool this turn")


@dataclass
class TurnResult:
    text: str
    cards: list[dict] = field(default_factory=list)
    guardrail: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    model: str | None = None
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    handoff_case_id: str | None = None


Event = tuple[str, Any]


def _with_handoff(cards: list[dict]) -> list[dict]:
    if any(card["kind"] in ("handoff", "concierge_case") for card in cards):
        return cards
    return [*cards, dict(HANDOFF_CARD)]


async def _consultation_card(ctx: TurnContext) -> list[dict]:
    """For a clinical redirect: the customer's own open consultation step, if they have one (verified lookup)."""
    outcome = await execute_tool(ctx, "get_my_journey", {})
    if outcome.is_error:
        return []
    for step in ctx.steps.values():
        if step.get("code") in BOOKABLE_STEP_CODES and step.get("status") in ("pending", "blocked") and step.get("service_category"):
            card = build_card(ctx, "journey_step", step["id"])
            return [card] if card else []
    return []


def _finish(ctx: TurnContext, result: TurnResult, outcome: str) -> TurnResult:
    result.tool_calls = ctx.calls
    result.handoff_case_id = ctx.handoff_case_id
    for call in ctx.calls:
        TOOL_CALLS.labels(call["name"], "ok" if call["ok"] else "error").inc()
    if ctx.rejected_cards:
        REJECTED_CARDS.inc(ctx.rejected_cards)
    TURNS.labels(outcome).inc()
    logger.info(
        "assistant turn outcome=%s guardrail=%s tools=%d cards=%d rejected_cards=%d",
        outcome,
        result.guardrail,
        len(ctx.calls),
        len(result.cards),
        ctx.rejected_cards,
    )
    return result


async def run_turn(*, llm: LLMProvider, ctx: TurnContext, history: list[dict[str, Any]], user_text: str) -> AsyncIterator[Event]:
    """``history`` is prior turns as plain-text messages; ``user_text`` is the new customer message.

    Raises LLMUnavailable (→ 503) before yielding anything when no model is configured and the turn
    is not answered by a code guardrail.
    """
    verdict = guardrails.classify_input(user_text)
    if verdict == "emergency":
        text = message("emergency", ctx.locale, number=settings.emergency_number)
        yield "delta", {"text": text}
        yield "result", _finish(ctx, TurnResult(text=text, cards=_with_handoff([]), guardrail="emergency"), "emergency")
        return
    if verdict == "clinical":
        text = message("clinical_redirect", ctx.locale)
        yield "delta", {"text": text}
        cards = _with_handoff(await _consultation_card(ctx))
        yield "result", _finish(ctx, TurnResult(text=text, cards=cards, guardrail="clinical_redirect"), "clinical_redirect")
        return

    if not llm.available:
        raise LLMUnavailable()

    system = build_system(ctx.locale, ctx.today)
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_text}]
    result = TurnResult(text="", model=llm.model)
    parts: list[str] = []
    streamed = False
    failure: str | None = None

    try:
        async with asyncio.timeout(settings.turn_timeout_seconds):
            for iteration in range(settings.max_tool_iterations + 1):
                step: ModelStep | None = None
                async for item in llm.stream_step(system=system, messages=messages, tools=TOOL_DEFINITIONS):
                    if isinstance(item, TextDelta):
                        if item.text:
                            if parts and not streamed:
                                yield "delta", {"text": "\n\n"}
                            streamed = True
                            yield "delta", {"text": item.text}
                    else:
                        step = item
                if step is None:
                    failure = "unable"
                    break
                streamed = False
                result.input_tokens += step.input_tokens
                result.output_tokens += step.output_tokens
                result.stop_reason = step.stop_reason
                result.model = step.model or result.model
                if step.text.strip():
                    parts.append(step.text.strip())

                if step.stop_reason == "refusal":
                    failure = "refusal"
                    break
                if not step.tool_calls:
                    break
                if step.stop_reason == "max_tokens":
                    # A truncated tool input can parse as a valid partial object: never run it.
                    failure = "unable"
                    break
                if iteration >= settings.max_tool_iterations or len(ctx.calls) + len(step.tool_calls) > settings.max_tool_calls_per_turn:
                    result.stop_reason = "tool_limit"
                    failure = "limit"
                    break

                for call in step.tool_calls:
                    yield "status", {"tool": call.name if call.name in _STATUS_TOOLS else "working"}
                outcomes = await asyncio.gather(*(execute_tool(ctx, call.name, call.input) for call in step.tool_calls))
                messages.append({"role": "assistant", "content": step.assistant_content})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": call.id, "content": outcome.content, **({"is_error": True} if outcome.is_error else {})}
                            for call, outcome in zip(step.tool_calls, outcomes, strict=True)
                        ],
                    }
                )
    except TimeoutError:
        result.stop_reason = "timeout"
        failure = "limit"
    except LLMUnavailable:
        if not parts and not ctx.calls:
            raise
        failure = "unable"
    except LLMError as exc:
        if not parts and not ctx.calls:
            raise
        logger.warning("assistant turn degraded after a provider error: %s", exc.code)
        failure = "unable"

    cards = list(ctx.cards)
    if ctx.case:
        cards.append(case_card(ctx.case))
    text = "\n\n".join(parts)

    if failure == "refusal":
        result.text, result.cards, result.guardrail = message("refusal", ctx.locale), _with_handoff(cards), "refusal"
        yield "replace", {"text": result.text}
        yield "result", _finish(ctx, result, "refusal")
        return

    output_verdict = guardrails.check_output(text, ctx.grounded_amounts()) if text else None
    if output_verdict == "clinical_redirect":
        result.text, result.cards, result.guardrail = message("clinical_redirect", ctx.locale), _with_handoff(cards), "clinical_redirect"
        yield "replace", {"text": result.text}
        yield "result", _finish(ctx, result, "clinical_output")
        return
    if output_verdict == "ungrounded":
        result.text, result.cards, result.guardrail = message("ungrounded", ctx.locale), _with_handoff(cards), "ungrounded"
        yield "replace", {"text": result.text}
        yield "result", _finish(ctx, result, "ungrounded")
        return

    if failure or not text:
        # Loop cap, timeout, truncation or an empty answer: keep what was verified, offer a person.
        result.guardrail = "limit" if failure == "limit" else result.guardrail
        fallback = message("ungrounded" if cards else "unable", ctx.locale)
        result.text = f"{text}\n\n{fallback}" if text and failure else (text or fallback)
        result.cards = _with_handoff(cards)
        if result.text != text:
            yield "replace", {"text": result.text}
        yield "result", _finish(ctx, result, failure or "empty")
        return

    result.text, result.cards = text, cards
    yield "result", _finish(ctx, result, "ok")


_STATUS_TOOLS = {
    "search_services",
    "get_service",
    "get_service_slots",
    "search_providers",
    "get_provider",
    "search_facilities",
    "get_facility",
    "get_my_journey",
    "list_my_appointments",
    "request_human_handoff",
}
