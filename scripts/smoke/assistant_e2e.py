"""End-to-end assistant smoke across real identity, provider, assessment, transformation, appointment,
concierge and ai-orchestrator services (events over NATS JetStream), with the deterministic fake LLM
(LLM_PROVIDER=fake) driving the real tool loop. Proves grounding against live data, the caller's
own identity on tool calls, the human hand-off, SSE streaming, isolation, no-key degradation and
erasure on account deletion.

Usage: python scripts/smoke/assistant_e2e.py
  env: IDENTITY, PROVIDER, ASSESSMENT, TRANSFORMATION, APPOINTMENT, CONCIERGE, AI (fake LLM),
       AI_NOKEY (an instance with LLM_PROVIDER=anthropic and no key), IDENTITY_DB, AI_DB (libpq URLs).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("journey_e2e", HERE / "journey_e2e.py")
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)  # type: ignore[union-attr]

AI = os.environ.get("AI", "http://127.0.0.1:8517")
AI_NOKEY = os.environ.get("AI_NOKEY", "")
CONCIERGE = os.environ.get("CONCIERGE", "http://127.0.0.1:8521")
AI_DB = os.environ.get("AI_DB", "")
check, register, key = j.check, j.register, j.key


def ask(c: httpx.Client, session: str, headers: dict, text: str) -> dict:
    return check(c.post(f"{AI}/v1/ai/sessions/{session}/messages", json={"content": text}, headers=headers))


def cards(turn: dict, kind: str) -> list[dict]:
    return [card for card in turn["cards"] if card["kind"] == kind]


def main() -> None:
    c = httpx.Client(timeout=60)
    customer, user_id, email = register(c, "assistant-customer")
    print(f"customer {email}")
    assert check(c.post(f"{AI}/v1/ai/sessions", json={}), 401)["code"] == "unauthorized"

    session = check(c.post(f"{AI}/v1/ai/sessions", json={"locale": "en"}, headers=customer), 201)
    sid = session["id"]
    assert session["assistant_available"] is True
    print("identity-service grants ai:chat to the customer role (session created via token introspection)")

    empty = ask(c, sid, customer, "what is next in my journey?")
    assert empty["cards"] == [] and "not started" in empty["content"], empty
    print("no journey yet → assistant says so, no cards")

    journey = check(c.post(f"{j.TE}/v1/journeys", json={"user_id": user_id, "primary_goals": ["skin_health"]}, headers={**customer, **key()}), 201)
    assessment = check(c.post(f"{j.AS}/v1/assessments", json={"user_id": user_id, "kind": "intake"}, headers={**customer, **key()}), 201)
    check(c.post(f"{j.AS}/v1/assessments/{assessment['id']}/submit", json={"responses": [{"question": "timeframe", "answer": "asap"}]}, headers={**customer, **key()}))
    j.wait_for(c, journey["id"], customer, "intake_assessment", "completed")
    consult = j.step(c, journey["id"], customer, "consultation")
    owner, offering = j.catalog(c, consult["service_category"])
    print(f"journey active; next step consultation ({consult['service_category']}); verified offering {offering['id']}")

    turn = ask(c, sid, customer, "what is next in my journey?")
    service_cards = cards(turn, "service")
    mine = next((card for card in service_cards if card["id"] == offering["id"]), None)
    assert mine, turn
    real = check(c.get(f"{j.PR}/v1/services/{offering['id']}"))
    assert mine["price"]["amount_minor"] == real["price"]["amount_minor"] and mine["price"]["currency"] == real["price"]["currency"]
    assert mine["milestone_id"] == consult["id"] and mine["href"] == f"/book/{offering['id']}?milestone={consult['id']}"
    print(f"card: {mine['title']} {mine['price']['amount']} {mine['price']['currency']} → {mine['href']} (price matches provider-service)")

    turn = ask(c, sid, customer, f"is {consult['service_category']} available this week? show slot times")
    card = next(card for card in cards(turn, "service") if card["id"] == offering["id"])
    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).date()
    real_slots = check(c.get(f"{j.AP}/v1/services/{offering['id']}/slots", params={"from": today.isoformat(), "to": (today + timedelta(days=14)).isoformat()}))["slots"]
    assert card["next_slots"] and card["next_slots"] == [s["scheduled_at"] for s in real_slots[:3]], (card["next_slots"], real_slots[:3])
    print(f"slots on card equal appointment-service slots: {card['next_slots'][0]} …")

    # No booking was made by the assistant.
    appts = check(c.get(f"{j.AP}/v1/appointments", params={"user_id": user_id}, headers=customer))["data"]
    assert appts == [], appts
    print("assistant created no appointment (booking stays in the normal UI)")

    turn = ask(c, sid, customer, "Which medication should I take for my skin?")
    assert turn["guardrail"] == "clinical_redirect" and [x["kind"] for x in turn["cards"]] == ["journey_step", "handoff"], turn
    turn = ask(c, sid, customer, "I have chest pain and can't breathe")
    assert turn["guardrail"] == "emergency" and "998" in turn["content"]
    print("clinical question → one-line redirect + consultation step; urgent symptoms → emergency pointer")

    turn = ask(c, sid, customer, "I would like to talk to a person")
    case_card = cards(turn, "concierge_case")[0]
    mine_cases = check(c.get(f"{CONCIERGE}/v1/concierge/cases", headers=customer))["data"]
    assert [x["id"] for x in mine_cases] == [case_card["id"]], mine_cases
    again = ask(c, sid, customer, "human please")
    assert cards(again, "concierge_case")[0]["id"] == case_card["id"]
    assert len(check(c.get(f"{CONCIERGE}/v1/concierge/cases", headers=customer))["data"]) == 1
    print(f"hand-off → concierge case {case_card['id']} owned by the customer (one per session)")

    with c.stream("POST", f"{AI}/v1/ai/sessions/{sid}/messages", json={"content": "find me a doctor"}, headers={**customer, "Accept": "text/event-stream"}) as response:
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())
    events = [line[7:] for line in raw.splitlines() if line.startswith("event: ")]
    assert events[0] == "turn" and events[-1] == "done" and "status" in events and "delta" in events, events
    done = json.loads(raw.strip().split("\n\n")[-1].split("data: ", 1)[1])["turn"]
    assert any(x["kind"] == "provider" for x in done["cards"])
    print(f"SSE stream events: {' '.join(dict.fromkeys(events))}")

    other, _, _ = register(c, "assistant-intruder")
    assert c.get(f"{AI}/v1/ai/sessions/{sid}", headers=other).status_code == 404
    assert c.post(f"{AI}/v1/ai/sessions/{sid}/messages", json={"content": "dental"}, headers=other).status_code == 404
    print("another customer cannot read or post to the session (404)")

    history = check(c.get(f"{AI}/v1/ai/sessions/{sid}", headers=customer))
    print(f"session holds {len(history['turns'])} turns")

    if AI_NOKEY:
        nokey = check(c.post(f"{AI_NOKEY}/v1/ai/sessions", json={}, headers=customer), 201)
        assert nokey["assistant_available"] is False
        r = c.post(f"{AI_NOKEY}/v1/ai/sessions/{nokey['id']}/messages", json={"content": "dental"}, headers=customer)
        assert r.status_code == 503 and r.json()["code"] == "service_unavailable", r.text
        print("instance without ANTHROPIC_API_KEY → assistant_available=false, messages 503 service_unavailable")

    if AI_DB:
        check(c.post(f"{j.ID}/v1/auth/delete-account", json={"password": j.PASSWORD}, headers=customer), 204)
        deadline = time.monotonic() + 20
        while True:
            left = subprocess.run([j.PSQL, AI_DB, "-qtAc", f"SELECT count(*) FROM ai_sessions WHERE user_id = '{user_id}'"], check=True, capture_output=True, text=True).stdout.strip()
            if left == "0":
                break
            if time.monotonic() > deadline:
                sys.exit(f"FAIL {left} assistant session(s) left 20s after account deletion")
            time.sleep(0.5)
        print("account deleted → auth.user_deleted over NATS erased the customer's assistant sessions")
    print("PASS assistant end to end")


if __name__ == "__main__":
    main()
