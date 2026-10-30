"""End-to-end booking smoke across real identity, provider and appointment services.

Creates everything through the public APIs (plus one SQL grant of the admin role to a reviewer
account), then: customer lists real slots → holds → requests → practitioner accepts.
Usage: python scripts/smoke/booking_e2e.py  (env: IDENTITY, PROVIDER, APPOINTMENT base URLs,
IDENTITY_DB = libpq URL of the identity database for the admin grant).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx

ID = os.environ.get("IDENTITY", "http://127.0.0.1:8301")
PR = os.environ.get("PROVIDER", "http://127.0.0.1:8305")
AP = os.environ.get("APPOINTMENT", "http://127.0.0.1:8307")
IDENTITY_DB = os.environ.get("IDENTITY_DB", "postgresql://healuxa:dev@127.0.0.1:5432/e2e_identity")
PSQL = os.environ.get("PSQL", "/opt/homebrew/opt/postgresql@16/bin/psql")
ADMIN_ROLE = "01JROLE00000000000000002"


def check(response: httpx.Response, status: int = 200) -> dict:
    if response.status_code != status:
        sys.exit(f"FAIL {response.request.method} {response.request.url} → {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def register(client: httpx.Client, label: str) -> tuple[dict, str]:
    body = {"identifier": f"{label}-{uuid.uuid4().hex[:8]}@example.com", "password": "Smoke-pass-1234", "locale": "en"}
    tokens = check(client.post(f"{ID}/v1/auth/register", json=body), 201)
    import base64, json

    payload = tokens["access_token"].split(".")[1]
    sub = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}, sub


def login(client: httpx.Client, identifier: str) -> dict:
    tokens = check(client.post(f"{ID}/v1/auth/login", json={"identifier": identifier, "password": "Smoke-pass-1234"}))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def main() -> None:
    c = httpx.Client(timeout=15)
    owner, owner_id = register(c, "doctor")
    admin_fac, admin_fac_id = register(c, "clinicadmin")
    customer, _ = register(c, "customer")

    reviewer_email = f"reviewer-{uuid.uuid4().hex[:8]}@example.com"
    check(c.post(f"{ID}/v1/auth/register", json={"identifier": reviewer_email, "password": "Smoke-pass-1234", "locale": "en"}), 201)
    subprocess.run(
        [PSQL, IDENTITY_DB, "-qtAc",
         f"INSERT INTO user_roles (user_id, role_id) SELECT id, '{ADMIN_ROLE}' FROM users WHERE identifier = '{reviewer_email}'"],
        check=True,
    )
    staff = login(c, reviewer_email)  # new token carries the admin permissions

    provider = check(c.post(f"{PR}/v1/providers", json={"type": "doctor", "display_name": "Dr. Smoke", "specialties": ["infectious diseases"], "languages": ["en", "ar"]}, headers=owner), 201)
    cred = check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials", json={"kind": "professional_license", "issuing_authority": "DHA", "number": f"DHA-{uuid.uuid4().hex[:6]}", "valid_until": str(date.today() + timedelta(days=365))}, headers=owner), 201)
    check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials/{cred['id']}/review", json={"decision": "verify"}, headers=staff))
    check(c.post(f"{PR}/v1/providers/{provider['id']}/status", json={"status": "active", "reason": "verified licence"}, headers=staff))

    facility = check(c.post(f"{PR}/v1/facilities", json={"type": "clinic", "name": "Smoke Clinic", "license_authority": "DHA", "license_number": f"F-{uuid.uuid4().hex[:6]}"}, headers=admin_fac), 201)
    check(c.post(f"{PR}/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff))
    branch = check(c.post(f"{PR}/v1/facilities/{facility['id']}/branches", json={"name": "Marina", "address_line": "1 Marina Walk", "city": "Dubai", "country": "AE", "timezone": "Asia/Dubai"}, headers=admin_fac), 201)
    check(c.put(f"{PR}/v1/branches/{branch['id']}/operating-hours", json={"windows": [{"weekday": d, "start": "08:00", "end": "20:00"} for d in range(7)]}, headers=admin_fac))
    aff = check(c.post(f"{PR}/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=owner), 201)
    check(c.post(f"{PR}/v1/affiliations/{aff['id']}/decision", json={"decision": "approve"}, headers=admin_fac))
    offering = check(c.post(f"{PR}/v1/providers/{provider['id']}/services", json={"branch_id": branch["id"], "category": "consultation", "name": "Consultation", "duration_minutes": 30, "buffer_minutes": 10, "price_type": "fixed", "professional_fee_minor": 60000, "facility_fee_minor": 15000}, headers=owner), 201)
    for weekday in range(7):
        check(c.post(f"{PR}/v1/providers/{provider['id']}/availability-rules", json={"branch_id": branch["id"], "weekday": weekday, "start": "09:00", "end": "17:00", "effective_from": str(date.today())}, headers=owner), 201)
    print("catalog ready: provider, facility, branch, affiliation, offering, 7 availability rules")

    start = datetime.now(UTC) + timedelta(days=1)
    slots = check(c.get(f"{AP}/v1/services/{offering['id']}/slots", params={"from": start.date().isoformat(), "to": (start + timedelta(days=2)).date().isoformat()}))
    assert slots["slots"], "no slots derived"
    print(f"slots: {len(slots['slots'])} in {slots['timezone']}, first {slots['slots'][0]['local_start']}")

    slot = slots["slots"][0]["scheduled_at"]
    hold = check(c.post(f"{AP}/v1/appointments", json={"service_id": offering["id"], "scheduled_at": slot}, headers={**customer, "Idempotency-Key": uuid.uuid4().hex}), 201)
    second = c.post(f"{AP}/v1/appointments", json={"service_id": offering["id"], "scheduled_at": slot}, headers={**owner, "Idempotency-Key": uuid.uuid4().hex})
    print(f"hold {hold['status']}; competing hold on same slot → {second.status_code}")
    requested = check(c.post(f"{AP}/v1/appointments/{hold['id']}/status", json={"transition": "submit"}, headers=customer))
    accepted = check(c.post(f"{AP}/v1/appointments/{hold['id']}/status", json={"transition": "accept"}, headers=owner))
    print(f"lifecycle: {hold['status']} → {requested['status']} → {accepted['status']} (payment_status={accepted['payment_status']})")
    print("PASS booking end to end")


if __name__ == "__main__":
    main()
