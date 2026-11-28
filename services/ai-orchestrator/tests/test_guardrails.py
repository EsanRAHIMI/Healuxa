"""Code guardrails: emergency pointer, clinical redirect, output checks, input limits, loop cap, refusal."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from ai_orchestrator.config import settings
from ai_orchestrator.domain import guardrails
from ai_orchestrator.llm.fake import FakeProvider
from conftest import ask
from platform_stub import MILESTONE, PlatformStub


@pytest.mark.parametrize(
    "text",
    ["I have crushing chest pain right now", "my friend is unconscious", "أشعر بألم في الصدر", "درد قفسه سینه دارم", "I want to kill myself"],
)
def test_emergency_language_is_detected(text: str) -> None:
    assert guardrails.classify_input(text) == "emergency"


@pytest.mark.parametrize(
    "text",
    ["What dosage of retinol should I use?", "Do I have eczema?", "Could this be an infection?", "Which medication is best for acne?", "Should I stop taking my pills?", "ما الجرعة المناسبة؟", "چه دارویی بخورم؟ کدام دارو"],
)
def test_clinical_questions_are_detected(text: str) -> None:
    assert guardrails.classify_input(text) == "clinical"


@pytest.mark.parametrize(
    "text",
    [
        "Which clinics offer dental cleaning?",
        "What is next in my journey?",
        "Can I book a dermatology consultation this week?",
        "How much is a hair consultation?",
        "What appointments do I have coming up?",
        "Do I have anything booked?",
        "Have I got a booking tomorrow?",
        "أريد حجز موعد أسنان",
        "هل لدي مواعيد قادمة؟",
        "آیا من نوبتی دارم؟",
    ],
)
def test_coordination_questions_pass_through(text: str) -> None:
    assert guardrails.classify_input(text) is None


def test_output_check_prices_and_dosing() -> None:
    allowed = {Decimal("450.00")}
    assert guardrails.check_output("The check-up is AED 450.", allowed) is None
    assert guardrails.check_output("It costs 1,250 AED.", allowed) == "ungrounded"
    assert guardrails.check_output("حوالي ٣٠٠ درهم", allowed) == "ungrounded"
    assert guardrails.check_output("Take 20 mg daily.", allowed) == "clinical_redirect"
    assert guardrails.check_output("You probably have rosacea.", allowed) == "clinical_redirect"
    assert guardrails.check_output("You have 2 upcoming appointments.", allowed) is None


async def test_emergency_turn_is_brief_and_skips_the_model(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    body = (await ask(client, session_id, auth_headers, "I have severe chest pain")).json()
    assert body["guardrail"] == "emergency"
    assert "998" in body["content"] and len(body["content"]) < 200
    assert [c["kind"] for c in body["cards"]] == ["handoff"]
    assert llm.requests == []


async def test_clinical_question_gets_one_sentence_and_a_consultation_card(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    body = (await ask(client, session_id, auth_headers, "Which medication should I take for my skin?")).json()
    assert body["guardrail"] == "clinical_redirect"
    assert body["content"].count(".") <= 1 and len(body["content"]) < 160
    kinds = [c["kind"] for c in body["cards"]]
    assert kinds == ["journey_step", "handoff"]
    assert body["cards"][0]["id"] == MILESTONE
    assert llm.requests == []


async def test_clinical_redirect_is_localised(client: AsyncClient, auth_headers: dict) -> None:
    sid = (await client.post("/v1/ai/sessions", json={"locale": "fa"}, headers=auth_headers)).json()["id"]
    body = (await ask(client, sid, auth_headers, "چه دارویی برای پوستم مصرف کنم؟")).json()
    assert body["guardrail"] == "clinical_redirect" and "متخصص" in body["content"]


async def test_model_dosing_text_is_replaced(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    body = (await ask(client, session_id, auth_headers, "dose-leak test")).json()
    assert body["guardrail"] == "clinical_redirect" and "mg" not in body["content"]


async def test_refusal_is_handled(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    body = (await ask(client, session_id, auth_headers, "refuse this")).json()
    assert body["guardrail"] == "refusal" and any(c["kind"] == "handoff" for c in body["cards"])


async def test_tool_loop_is_capped(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider, monkeypatch: pytest.MonkeyPatch, platform: PlatformStub) -> None:
    monkeypatch.setattr(settings, "max_tool_iterations", 3)
    body = (await ask(client, session_id, auth_headers, "loop forever")).json()
    assert body["guardrail"] == "limit"
    assert len(llm.requests) == 4  # initial call + 3 tool rounds, then stop
    assert len([p for p in platform.paths() if p == "GET /v1/services"]) == 3
    assert any(c["kind"] == "handoff" for c in body["cards"])


async def test_message_size_limit(client: AsyncClient, session_id: str, auth_headers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_message_chars", 50)
    too_long = await ask(client, session_id, auth_headers, "x" * 51)
    assert too_long.status_code == 422 and too_long.json()["code"] == "validation_error"
    assert "xxxx" not in too_long.text  # the message is never echoed back
    blank = await ask(client, session_id, auth_headers, "   ")
    assert blank.status_code == 422
    huge = await client.post(f"/v1/ai/sessions/{session_id}/messages", json={"content": "y" * 9000}, headers=auth_headers)
    assert huge.status_code == 422 and "yyyy" not in huge.text


async def test_unknown_fields_are_rejected(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    response = await client.post(f"/v1/ai/sessions/{session_id}/messages", json={"content": "hi", "role": "system"}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.parametrize(("text", "expected"), [("What dose?", "en"), ("ما الجرعة؟", "ar"), ("چه دارویی بخورم؟", "fa"), ("123", "ar")])
def test_reply_language_follows_the_message_script(text: str, expected: str) -> None:
    from ai_orchestrator.domain.messages import reply_language

    assert reply_language(text, "ar") == expected


async def test_guardrail_reply_uses_the_message_language_not_the_session_locale(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    body = (await ask(client, session_id, auth_headers, "ما الجرعة المناسبة لي؟")).json()
    assert body["guardrail"] == "clinical_redirect" and "مختص" in body["content"]


def test_web_starter_prompts_are_not_misread_as_clinical_or_urgent() -> None:
    import json
    from pathlib import Path

    messages = Path(__file__).resolve().parents[3] / "packages" / "i18n" / "messages"
    for locale in ("en", "ar", "fa"):
        starters = json.loads((messages / f"{locale}.json").read_text(encoding="utf-8"))["assistant"]["starter"]
        for key, text in starters.items():
            assert guardrails.classify_input(text.replace("{goal}", "skin")) is None, f"{locale}:{key}"
