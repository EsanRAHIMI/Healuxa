"""Tool grounding: cards and prices come only from this turn's tool results, with the caller's identity."""

from __future__ import annotations

import json

from httpx import AsyncClient

from ai_orchestrator.llm.fake import FakeProvider, FakeStep
from conftest import ask
from platform_stub import (
    APPOINTMENT,
    CASE,
    FACILITY,
    MILESTONE,
    PROVIDER_OK,
    PROVIDER_UNVERIFIED,
    SERVICE_DENTAL,
    SERVICE_DENTAL_2,
    SERVICE_UNVERIFIED,
    TOKEN,
    PlatformStub,
)


def _cards(body: dict, kind: str) -> list[dict]:
    return [c for c in body["cards"] if c["kind"] == kind]


async def test_service_cards_carry_real_price_and_booking_link(client: AsyncClient, session_id: str, auth_headers: dict, platform: PlatformStub) -> None:
    response = await ask(client, session_id, auth_headers, "I am looking for dental care")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "assistant" and body["guardrail"] is None
    cards = {c["id"]: c for c in _cards(body, "service")}
    assert set(cards) == {SERVICE_DENTAL, SERVICE_DENTAL_2}
    first = cards[SERVICE_DENTAL]
    assert first["title"] == "Dental check-up and cleaning"
    assert first["price"] == {"amount_minor": 45000, "amount": "450.00", "currency": "AED"} and first["price_type"] == "fixed"
    assert first["provider_name"] == "Dr. Layla Haddad"
    assert first["href"] == f"/book/{SERVICE_DENTAL}"
    assert cards[SERVICE_DENTAL_2]["price"] is None and cards[SERVICE_DENTAL_2]["price_type"] == "on_request"
    # Public catalog reads are anonymous: the customer's token is not sent where it is not needed.
    catalog = [r for r in platform.requests if r.url.path == "/v1/services"]
    assert catalog and "authorization" not in catalog[0].headers


async def test_offerings_of_unverified_practitioners_are_never_shown(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    body = (await ask(client, session_id, auth_headers, "dental")).json()
    assert SERVICE_UNVERIFIED not in json.dumps(body)
    # ...and the model never even saw it.
    assert SERVICE_UNVERIFIED not in json.dumps(llm.requests, default=str)
    assert PROVIDER_UNVERIFIED not in json.dumps(llm.requests, default=str)


async def test_invented_card_and_price_are_dropped(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    body = (await ask(client, session_id, auth_headers, "please invent something")).json()
    assert _cards(body, "service") == []
    assert "99,999" not in body["content"] and "Imaginary" not in body["content"]
    assert body["guardrail"] == "ungrounded"
    assert _cards(body, "handoff")


async def test_price_in_text_must_match_a_tool_result(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    def quote_price(amount: str):
        def script(messages):
            if isinstance(messages[-1]["content"], str):
                return FakeStep(calls=[("get_service", {"service_id": SERVICE_DENTAL})])
            return FakeStep(text=f"The check-up costs AED {amount}.")

        return script

    llm.script = quote_price("450")
    grounded = (await ask(client, session_id, auth_headers, "how much is it")).json()
    assert grounded["guardrail"] is None and "AED 450" in grounded["content"]

    llm.script = quote_price("399")
    invented = (await ask(client, session_id, auth_headers, "how much is it")).json()
    assert invented["guardrail"] == "ungrounded" and "399" not in invented["content"]


async def test_card_for_entity_from_an_earlier_turn_is_rejected(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    await ask(client, session_id, auth_headers, "dental")

    def script(messages):
        if isinstance(messages[-1]["content"], str):
            return FakeStep(calls=[("present_cards", {"cards": [{"kind": "service", "id": SERVICE_DENTAL, "milestone_id": None}]})])
        return FakeStep(text="Here you go.")

    llm.script = script
    body = (await ask(client, session_id, auth_headers, "show me the first one again")).json()
    assert _cards(body, "service") == []
    # History told the model which cards were shown, so it can re-fetch by id.
    history = llm.requests[-1]["messages"]
    assert any(m["role"] == "assistant" and f"service {SERVICE_DENTAL}" in m["content"] for m in history if isinstance(m["content"], str))


async def test_journey_links_booking_to_the_open_step(client: AsyncClient, session_id: str, auth_headers: dict, platform: PlatformStub, user_id: str) -> None:
    body = (await ask(client, session_id, auth_headers, "what is next in my journey?")).json()
    service = next(c for c in _cards(body, "service") if c["id"] == SERVICE_DENTAL)
    assert service["milestone_id"] == MILESTONE
    assert service["href"] == f"/book/{SERVICE_DENTAL}?milestone={MILESTONE}"
    journey_calls = [r for r in platform.requests if r.url.path == f"/v1/journeys/{user_id}"]
    assert journey_calls and journey_calls[0].headers["authorization"] == f"Bearer {TOKEN}"


async def test_model_cannot_attach_a_foreign_milestone(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    def script(messages):
        if isinstance(messages[-1]["content"], str):
            return FakeStep(calls=[("get_service", {"service_id": SERVICE_DENTAL})])
        if len(messages) == 3:
            return FakeStep(calls=[("present_cards", {"cards": [{"kind": "service", "id": SERVICE_DENTAL, "milestone_id": "01SOMEONEELSESMILESTONE0001"}]})])
        return FakeStep(text="Here it is.")

    llm.script = script
    body = (await ask(client, session_id, auth_headers, "book the check-up")).json()
    card = _cards(body, "service")[0]
    assert card["milestone_id"] is None and card["href"] == f"/book/{SERVICE_DENTAL}"


async def test_slots_on_cards_come_from_the_slots_tool(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    body = (await ask(client, session_id, auth_headers, "is dental available this week? show slot times")).json()
    card = _cards(body, "service")[0]
    assert card["next_slots"] == ["2030-01-02T06:00:00Z", "2030-01-03T06:00:00Z", "2030-01-04T06:00:00Z"]
    assert card["timezone"] == "Asia/Dubai"
    without = (await ask(client, session_id, auth_headers, "dental")).json()
    assert _cards(without, "service")[0]["next_slots"] == []


async def test_providers_facilities_and_appointments_cards(client: AsyncClient, session_id: str, auth_headers: dict) -> None:
    providers = (await ask(client, session_id, auth_headers, "find me a doctor")).json()
    assert [c["id"] for c in _cards(providers, "provider")] == [PROVIDER_OK]
    assert _cards(providers, "provider")[0]["href"] == f"/providers/{PROVIDER_OK}"
    facilities = (await ask(client, session_id, auth_headers, "which clinic?")).json()
    assert _cards(facilities, "facility")[0] == {"kind": "facility", "id": FACILITY, "title": "Marina Dental Clinic", "facility_type": "clinic", "href": f"/facilities/{FACILITY}"}
    appointments = (await ask(client, session_id, auth_headers, "my upcoming appointment")).json()
    assert _cards(appointments, "appointment")[0]["href"] == f"/account/bookings/{APPOINTMENT}"


async def test_model_receives_minimum_personal_data(client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider, user_id: str) -> None:
    await ask(client, session_id, auth_headers, "what is next in my journey?")
    await ask(client, session_id, auth_headers, "my upcoming appointment")
    await ask(client, session_id, auth_headers, "find me a doctor")
    await ask(client, session_id, auth_headers, "which clinic?")
    sent = json.dumps(llm.requests, default=str)
    assert user_id not in sent
    assert TOKEN not in sent
    assert "owner-user-id-must-not-leak" not in sent and "must-not-leak" not in sent


async def test_handoff_creates_one_concierge_case_without_message_text(client: AsyncClient, session_id: str, auth_headers: dict, platform: PlatformStub) -> None:
    secret = "my private situation is XYZZY"
    body = (await ask(client, session_id, auth_headers, f"I want to talk to a person. {secret}")).json()
    case = _cards(body, "concierge_case")[0]
    assert case["id"] == CASE and case["href"] == f"/account/concierge/{CASE}"
    assert len(platform.cases_created) == 1
    created = platform.cases_created[0]
    assert created["body"] == {"category": "other", "languages": ["en"], "needs_note": "Requested from the Healuxa assistant."}
    assert created["idempotency_key"] == f"ai-handoff-{session_id}"
    # Asking again in the same session reuses the open request instead of opening another.
    again = (await ask(client, session_id, auth_headers, "human please")).json()
    assert _cards(again, "concierge_case")[0]["id"] == CASE
    assert len(platform.cases_created) == 1
    session = (await client.get(f"/v1/ai/sessions/{session_id}", headers=auth_headers)).json()
    assert session["handoff_case_id"] == CASE


async def test_assistant_has_no_booking_or_payment_tools(platform: PlatformStub, client: AsyncClient, session_id: str, auth_headers: dict, llm: FakeProvider) -> None:
    from ai_orchestrator.domain.tools import TOOL_NAMES

    assert not [n for n in TOOL_NAMES if any(w in n for w in ("book", "pay", "appointment_create", "cancel", "hold"))]
    for prompt in ("dental", "what is next in my journey?", "my upcoming appointment", "is dental available? slot"):
        await ask(client, session_id, auth_headers, prompt)
    writes = [p for p in platform.paths() if not p.startswith("GET ")]
    assert writes == []


async def test_tool_failure_degrades_to_handoff(client: AsyncClient, session_id: str, auth_headers: dict, platform: PlatformStub) -> None:
    platform.fail_services = True

    body = (await ask(client, session_id, auth_headers, "dental")).json()
    assert _cards(body, "service") == []
    assert body["content"]


async def test_no_journey_yet(client: AsyncClient, session_id: str, auth_headers: dict, platform: PlatformStub) -> None:
    platform.has_journey = False
    body = (await ask(client, session_id, auth_headers, "what is next in my journey?")).json()
    assert body["cards"] == [] and "not started" in body["content"]
