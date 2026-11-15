"""Deterministic LLM double (``LLM_PROVIDER=fake``) for tests and local end-to-end runs.

It drives the real tool loop from keywords in the last customer message, and reacts to tool results
the way a model would, so the whole pipeline (tools → grounding → cards → guardrails → streaming) is
exercised without a vendor call. Tests can also inject an explicit script. Never used in production
(config refuses it when APP_ENV is production/staging).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from ai_orchestrator.domain.tools import KNOWN_CATEGORIES
from ai_orchestrator.llm.base import ModelStep, TextDelta, ToolCall

Script = Callable[[list[dict[str, Any]]], "FakeStep"]


class FakeStep:
    def __init__(self, text: str = "", calls: list[tuple[str, dict]] | None = None, stop_reason: str | None = None) -> None:
        self.text = text
        self.calls = calls or []
        self.stop_reason = stop_reason


def last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(message["content"], str):
            return message["content"]
    return ""


def tool_results(messages: list[dict[str, Any]]) -> list[tuple[str, dict]]:
    """(tool name, parsed result) pairs of the current turn, oldest first."""
    names: dict[str, str] = {}
    out: list[tuple[str, dict]] = []
    for message in messages:
        if not isinstance(message["content"], list):
            names, out = {}, []  # a plain-text message starts a new turn
            continue
        for block in message["content"]:
            if block.get("type") == "tool_use":
                names[block["id"]] = block["name"]
            elif block.get("type") == "tool_result":
                try:
                    parsed = json.loads(block["content"])
                except (TypeError, ValueError):
                    parsed = {}
                out.append((names.get(block["tool_use_id"], "?"), parsed))
    return out


def default_script(messages: list[dict[str, Any]]) -> FakeStep:
    text = last_user_text(messages).lower()
    results = tool_results(messages)
    done = [name for name, _ in results]

    if "loop" in text:
        return FakeStep(calls=[("search_services", {"category": "dental"})])
    if "invent" in text:
        if not done:
            return FakeStep(calls=[("present_cards", {"cards": [{"kind": "service", "id": "01INVENTEDSERVICE0000000000", "milestone_id": None}]})])
        return FakeStep(text="Dr. Imaginary offers this for AED 99,999.")
    if "dose-leak" in text:
        return FakeStep(text="You should take 500 mg twice a day.")
    if "refuse" in text:
        return FakeStep(stop_reason="refusal")

    if not done:
        if any(word in text for word in ("person", "human", "coordinator")):
            return FakeStep(calls=[("request_human_handoff", {"category": "other"})])
        if "appointment" in text:
            return FakeStep(calls=[("list_my_appointments", {})])
        if "journey" in text or "next" in text:
            return FakeStep(calls=[("get_my_journey", {})])
        if "clinic" in text or "hospital" in text:
            return FakeStep(calls=[("search_facilities", {"city": None})])
        if "practitioner" in text or "doctor" in text:
            return FakeStep(calls=[("search_providers", {"specialty": None, "language": None, "city": None})])
        for category in KNOWN_CATEGORIES:
            if category in text:
                return FakeStep(text="Let me check.", calls=[("search_services", {"category": category})])
        return FakeStep(text="I can help you find verified services, check your journey or connect you with a coordinator.")

    name, result = results[-1]
    if name == "get_my_journey":
        if not result.get("has_journey"):
            return FakeStep(text="You have not started a journey yet.")
        action = next((a for a in result.get("next_actions", []) if a.get("service_category")), None)
        if action and "search_services" not in done:
            return FakeStep(calls=[("search_services", {"category": action["service_category"]})])
        step = next((s for p in result.get("phases", []) for s in p["steps"] if s["status"] == "pending"), None)
        if step:
            return FakeStep(calls=[("present_cards", {"cards": [{"kind": "journey_step", "id": step["id"], "milestone_id": None}]})])
        return FakeStep(text="Your journey is up to date.")
    if name == "search_services":
        services = result.get("services", [])
        if not services:
            return FakeStep(text="I could not find a verified service for that yet.")
        if "slot" in text or "available" in text:
            return FakeStep(calls=[("get_service_slots", {"service_id": services[0]["id"], "from_date": None, "to_date": None})])
        return FakeStep(calls=[("present_cards", {"cards": [{"kind": "service", "id": s["id"], "milestone_id": None} for s in services[:3]]})])
    if name == "get_service_slots":
        return FakeStep(calls=[("present_cards", {"cards": [{"kind": "service", "id": result["service_id"], "milestone_id": None}]})])
    if name == "search_providers":
        return FakeStep(calls=[("present_cards", {"cards": [{"kind": "provider", "id": p["id"], "milestone_id": None} for p in result.get("providers", [])[:3]]})])
    if name == "search_facilities":
        return FakeStep(calls=[("present_cards", {"cards": [{"kind": "facility", "id": f["id"], "milestone_id": None} for f in result.get("facilities", [])[:3]]})])
    if name == "list_my_appointments":
        appointments = result.get("appointments", [])
        if not appointments:
            return FakeStep(text="You have no upcoming appointments.")
        return FakeStep(calls=[("present_cards", {"cards": [{"kind": "appointment", "id": a["id"], "milestone_id": None} for a in appointments[:3]]})])
    if name == "request_human_handoff":
        return FakeStep(text="A coordinator will take it from here." if result.get("handed_off") else "I could not reach a coordinator just now.")
    if name == "present_cards":
        return FakeStep(text="Here are verified options you can book." if result.get("shown") else "I could not verify that.")
    return FakeStep(text="Done.")


class FakeProvider:
    name = "fake"
    model = "fake-deterministic"

    def __init__(self, script: Script | None = None, *, available: bool = True) -> None:
        self.script = script or default_script
        self._available = available
        self.requests: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return self._available

    async def stream_step(
        self, *, system: list[dict[str, Any]], messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[TextDelta | ModelStep]:
        self.requests.append({"system": system, "messages": [dict(m) for m in messages], "tools": tools})
        step = self.script(messages)
        index = len(self.requests)
        content: list[dict[str, Any]] = []
        if step.text:
            for word in step.text.split(" "):
                yield TextDelta(word + " ")
            content.append({"type": "text", "text": step.text})
        calls = [ToolCall(id=f"fake_{index}_{i}", name=name, input=args) for i, (name, args) in enumerate(step.calls)]
        content.extend({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in calls)
        yield ModelStep(
            assistant_content=content,
            text=step.text,
            tool_calls=calls,
            stop_reason=step.stop_reason or ("tool_use" if calls else "end_turn"),
            input_tokens=0,
            output_tokens=0,
            model=self.model,
        )
