"""End-to-end journey smoke across real identity, provider, assessment, transformation and
appointment services, with events flowing over NATS JetStream (NATS_ENABLED=true on all of them).

goal → generated plan → intake assessment (event) opens the consult stage → the consultation step
is booked through the normal booking flow with `milestone_id` → the step follows the appointment.
Usage: python scripts/smoke/journey_e2e.py  (env: IDENTITY, PROVIDER, ASSESSMENT, TRANSFORMATION,
APPOINTMENT base URLs; IDENTITY_DB = libpq URL of the identity database for the admin grant).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx

ID = os.environ.get("IDENTITY", "http://127.0.0.1:8401")
PR = os.environ.get("PROVIDER", "http://127.0.0.1:8405")
AS = os.environ.get("ASSESSMENT", "http://127.0.0.1:8403")
TE = os.environ.get("TRANSFORMATION", "http://127.0.0.1:8400")
AP = os.environ.get("APPOINTMENT", "http://127.0.0.1:8407")
IDENTITY_DB = os.environ.get("IDENTITY_DB", "postgresql://healuxa:dev@127.0.0.1:5432/journey_e2e_identity")
PSQL = os.environ.get("PSQL", "/opt/homebrew/opt/postgresql@16/bin/psql")
ADMIN_ROLE = "01JROLE00000000000000002"
PASSWORD = "Smoke-pass-1234"


def check(response: httpx.Response, status: int = 200) -> dict:
    if response.status_code != status:
        sys.exit(f"FAIL {response.request.method} {response.request.url} → {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def register(c: httpx.Client, label: str) -> tuple[dict, str, str]:
    email = f"{label}-{uuid.uuid4().hex[:8]}@example.com"
    tokens = check(c.post(f"{ID}/v1/auth/register", json={"identifier": email, "password": PASSWORD, "locale": "en"}), 201)
    payload = tokens["access_token"].split(".")[1]
    sub = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}, sub, email


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


def step(c: httpx.Client, journey_id: str, headers: dict, code: str) -> dict:
    roadmap = check(c.get(f"{TE}/v1/journeys/{journey_id}/roadmap", headers=headers))
    return next(m for p in roadmap["phases"] for m in p["milestones"] if m["code"] == code)


def wait_for(c: httpx.Client, journey_id: str, headers: dict, code: str, status: str, seconds: float = 20) -> dict:
    deadline = time.monotonic() + seconds
    while True:
        current = step(c, journey_id, headers, code)
        if current["status"] == status:
            return current
        if time.monotonic() > deadline:
            sys.exit(f"FAIL step {code} is {current['status']!r}, expected {status!r} within {seconds}s (events not flowing?)")
        time.sleep(0.5)


def catalog(c: httpx.Client, category: str) -> tuple[dict, dict]:
    owner, _, _ = register(c, "doctor")
    admin_fac, _, _ = register(c, "clinicadmin")
    _, _, reviewer_email = register(c, "reviewer")
    subprocess.run(
        [PSQL, IDENTITY_DB, "-qtAc",
         f"INSERT INTO user_roles (user_id, role_id) SELECT id, '{ADMIN_ROLE}' FROM users WHERE identifier = '{reviewer_email}'"],
        check=True,
    )
    tokens = check(c.post(f"{ID}/v1/auth/login", json={"identifier": reviewer_email, "password": PASSWORD}))
    staff = {"Authorization": f"Bearer {tokens['access_token']}"}

    provider = check(c.post(f"{PR}/v1/providers", json={"accept_content_license": True, "type": "doctor", "display_name": "Dr. Journey Smoke", "specialties": [category], "languages": ["en", "ar"]}, headers=owner), 201)
    cred = check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials", json={"kind": "professional_license", "issuing_authority": "DHA", "number": f"DHA-{uuid.uuid4().hex[:6]}", "valid_until": str(date.today() + timedelta(days=365))}, headers=owner), 201)
    check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials/{cred['id']}/review", json={"decision": "verify"}, headers=staff))
    check(c.post(f"{PR}/v1/providers/{provider['id']}/status", json={"status": "active", "reason": "verified licence"}, headers=staff))
    facility = check(c.post(f"{PR}/v1/facilities", json={"accept_content_license": True, "type": "clinic", "name": "Journey Smoke Clinic", "license_authority": "DHA", "license_number": f"F-{uuid.uuid4().hex[:6]}"}, headers=admin_fac), 201)
    check(c.post(f"{PR}/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff))
    branch = check(c.post(f"{PR}/v1/facilities/{facility['id']}/branches", json={"name": "Marina", "address_line": "1 Marina Walk", "city": "Dubai", "country": "AE", "timezone": "Asia/Dubai"}, headers=admin_fac), 201)
    check(c.put(f"{PR}/v1/branches/{branch['id']}/operating-hours", json={"windows": [{"weekday": d, "start": "08:00", "end": "20:00"} for d in range(7)]}, headers=admin_fac))
    aff = check(c.post(f"{PR}/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=owner), 201)
    check(c.post(f"{PR}/v1/affiliations/{aff['id']}/decision", json={"decision": "approve"}, headers=admin_fac))
    offering = check(c.post(f"{PR}/v1/providers/{provider['id']}/services", json={"branch_id": branch["id"], "category": category, "name": "Dermatology consultation", "duration_minutes": 30, "buffer_minutes": 10, "price_type": "fixed", "professional_fee_minor": 60000, "facility_fee_minor": 15000}, headers=owner), 201)
    for weekday in range(7):
        check(c.post(f"{PR}/v1/providers/{provider['id']}/availability-rules", json={"branch_id": branch["id"], "weekday": weekday, "start": "09:00", "end": "17:00", "effective_from": str(date.today())}, headers=owner), 201)
    return owner, offering


def main() -> None:
    c = httpx.Client(timeout=15)
    customer, user_id, email = register(c, "customer")
    print(f"customer {email}")

    journey = check(c.post(f"{TE}/v1/journeys", json={"user_id": user_id, "primary_goals": ["skin_health"]}, headers={**customer, **key()}), 201)
    roadmap = check(c.get(f"{TE}/v1/journeys/{journey['id']}/roadmap", headers=customer))
    print(f"journey {journey['status']}: " + " | ".join(f"{p['code']}[{p['status']}] {len(p['milestones'])} step(s)" for p in roadmap["phases"]))
    assert check(c.post(f"{TE}/v1/journeys", json={"user_id": user_id, "primary_goals": ["longevity"]}, headers={**customer, **key()}), 409)["code"] == "conflict"

    assessment = check(c.post(f"{AS}/v1/assessments", json={"user_id": user_id, "kind": "intake"}, headers={**customer, **key()}), 201)
    responses = [{"question": "timeframe", "answer": "asap"}, {"question": "city", "answer": "dubai"}, {"question": "language", "answer": "en"}]
    check(c.post(f"{AS}/v1/assessments/{assessment['id']}/submit", json={"responses": responses}, headers={**customer, **key()}))
    started = time.monotonic()
    wait_for(c, journey["id"], customer, "intake_assessment", "completed")
    status = check(c.get(f"{TE}/v1/journeys/{user_id}", headers=customer))["status"]
    print(f"intake assessment → step completed via event in {time.monotonic() - started:.1f}s; journey {status}")
    assert status == "active"

    actions = check(c.get(f"{TE}/v1/journeys/{journey['id']}/next-actions", headers=customer))
    consult = step(c, journey["id"], customer, "consultation")
    assert actions[0]["milestone_id"] == consult["id"] and actions[0]["action_type"] == "book"
    category = consult["service_category"]

    owner, offering = catalog(c, category)
    listed = check(c.get(f"{PR}/v1/services", params={"category": category}))["data"]
    assert any(o["id"] == offering["id"] for o in listed), "offering not discoverable by the step's category"
    print(f"next action: book {category!r}; {len(listed)} matching verified offering(s)")

    start = datetime.now(UTC) + timedelta(days=1)
    slots = check(c.get(f"{AP}/v1/services/{offering['id']}/slots", params={"from": start.date().isoformat(), "to": (start + timedelta(days=2)).date().isoformat()}))["slots"]
    hold = check(c.post(f"{AP}/v1/appointments", json={"service_id": offering["id"], "scheduled_at": slots[0]["scheduled_at"], "milestone_id": consult["id"]}, headers={**customer, **key()}), 201)
    check(c.post(f"{AP}/v1/appointments/{hold['id']}/status", json={"transition": "submit"}, headers=customer))
    scheduled = wait_for(c, journey["id"], customer, "consultation", "scheduled")
    assert scheduled["appointment_id"] == hold["id"]
    print(f"booking with milestone_id → step scheduled for {scheduled['scheduled_at']}")

    # Another customer naming this step in their own booking must not move it.
    intruder, _, _ = register(c, "intruder")
    other = check(c.post(f"{AP}/v1/appointments", json={"service_id": offering["id"], "scheduled_at": slots[-1]["scheduled_at"], "milestone_id": consult["id"]}, headers={**intruder, **key()}), 201)
    check(c.post(f"{AP}/v1/appointments/{other['id']}/status", json={"transition": "submit"}, headers=intruder))
    check(c.post(f"{AP}/v1/appointments/{other['id']}/status", json={"transition": "cancel", "reason_code": "customer_request"}, headers=intruder))
    time.sleep(2)
    assert step(c, journey["id"], customer, "consultation")["appointment_id"] == hold["id"], "foreign booking moved the step"
    print("another user's booking naming the same step → ignored")

    check(c.post(f"{AP}/v1/appointments/{hold['id']}/status", json={"transition": "accept"}, headers=owner))
    check(c.post(f"{AP}/v1/appointments/{hold['id']}/status", json={"transition": "cancel", "reason_code": "customer_request"}, headers=customer))
    released = wait_for(c, journey["id"], customer, "consultation", "pending")
    assert released["appointment_id"] is None
    print("customer cancels → step back to pending")

    done = check(c.post(f"{TE}/v1/journeys/{journey['id']}/milestones/{consult['id']}/complete", headers={**customer, **key()}))
    roadmap = check(c.get(f"{TE}/v1/journeys/{journey['id']}/roadmap", headers=customer))
    print(f"step marked {done['status']}; stages: " + ", ".join(f"{p['code']}={p['status']}" for p in roadmap["phases"]))
    assert [p["status"] for p in roadmap["phases"]] == ["completed", "completed", "in_progress", "pending"]
    print("PASS journey end to end")


if __name__ == "__main__":
    main()
