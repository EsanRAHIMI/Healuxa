"""End-to-end medical-records smoke across real identity, provider, appointment and profile services.

customer books a consultation → uploads a lab result (encrypted at rest) → shares it from the booking
with the practitioner → the practitioner (verified against provider-service) sees it in "shared with
me" and downloads it → a practitioner of another practice is refused → the customer stops sharing →
the practitioner gets 403 immediately → facility staff access works while they are staff and stops
when they are removed → the customer's access log shows every step, including the refusals → the
grant/revoke/access events reach NATS JetStream with identifiers only.

Usage: python scripts/smoke/records_e2e.py
  env: IDENTITY, PROVIDER, APPOINTMENT, PROFILE base URLs; IDENTITY_DB (libpq URL, for the admin grant);
       PROFILE_MONGODB_URI + PROFILE_MONGODB_DATABASE (to inspect stored bytes); NATS_URL (optional).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx

ID = os.environ.get("IDENTITY", "http://127.0.0.1:8601")
PR = os.environ.get("PROVIDER", "http://127.0.0.1:8605")
AP = os.environ.get("APPOINTMENT", "http://127.0.0.1:8607")
PF = os.environ.get("PROFILE", "http://127.0.0.1:8602")
IDENTITY_DB = os.environ.get("IDENTITY_DB", "postgresql://healuxa:dev@127.0.0.1:5432/rec_e2e_identity")
MONGO_URI = os.environ.get("PROFILE_MONGODB_URI", "mongodb://127.0.0.1:27020/?replicaSet=rs0&directConnection=true")
MONGO_DB = os.environ.get("PROFILE_MONGODB_DATABASE", "rec_e2e_profile_smoke_test")
NATS_URL = os.environ.get("NATS_URL", "nats://127.0.0.1:4422")
PSQL = os.environ.get("PSQL", "/opt/homebrew/opt/postgresql@16/bin/psql")
ADMIN_ROLE = "01JROLE00000000000000002"
PASSWORD = "Smoke-pass-1234"
SECRET_TITLE = f"Smoke lipid panel {uuid.uuid4().hex[:6]}"
PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n" + b"LDL 2.9 mmol/L " * 40 + b"\n%%EOF\n"


def check(response: httpx.Response, status: int = 200):
    if response.status_code != status:
        sys.exit(f"FAIL {response.request.method} {response.request.url} → {response.status_code} (wanted {status}): {response.text[:400]}")
    ctype = response.headers.get("content-type", "")
    return response.json() if response.content and ctype.startswith("application/json") else response


def register(c: httpx.Client, label: str) -> tuple[dict, str, str]:
    email = f"{label}-{uuid.uuid4().hex[:8]}@example.com"
    tokens = check(c.post(f"{ID}/v1/auth/register", json={"identifier": email, "password": PASSWORD, "locale": "en"}), 201)
    payload = tokens["access_token"].split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    assert "records:manage" in claims.get("perms", []), "identity migration 0011 not applied"
    return {"Authorization": f"Bearer {tokens['access_token']}"}, claims["sub"], email


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


def practice(c: httpx.Client, staff: dict, name: str) -> dict:
    owner, owner_id, _ = register(c, "doctor")
    admin, admin_id, _ = register(c, "clinicadmin")
    provider = check(c.post(f"{PR}/v1/providers", json={"accept_content_license": True, "type": "doctor", "display_name": name, "specialties": ["dermatology"], "languages": ["en"]}, headers=owner), 201)
    cred = check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials", json={"kind": "professional_license", "issuing_authority": "DHA", "number": f"DHA-{uuid.uuid4().hex[:6]}", "valid_until": str(date.today() + timedelta(days=365))}, headers=owner), 201)
    check(c.post(f"{PR}/v1/providers/{provider['id']}/credentials/{cred['id']}/review", json={"decision": "verify"}, headers=staff))
    check(c.post(f"{PR}/v1/providers/{provider['id']}/status", json={"status": "active", "reason": "verified licence"}, headers=staff))
    facility = check(c.post(f"{PR}/v1/facilities", json={"accept_content_license": True, "type": "clinic", "name": f"{name} Clinic", "license_authority": "DHA", "license_number": f"F-{uuid.uuid4().hex[:6]}"}, headers=admin), 201)
    check(c.post(f"{PR}/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff))
    branch = check(c.post(f"{PR}/v1/facilities/{facility['id']}/branches", json={"name": "Marina", "address_line": "1 Marina Walk", "city": "Dubai", "country": "AE", "timezone": "Asia/Dubai"}, headers=admin), 201)
    check(c.put(f"{PR}/v1/branches/{branch['id']}/operating-hours", json={"windows": [{"weekday": d, "start": "08:00", "end": "20:00"} for d in range(7)]}, headers=admin))
    aff = check(c.post(f"{PR}/v1/affiliations", json={"provider_id": provider["id"], "branch_id": branch["id"]}, headers=owner), 201)
    check(c.post(f"{PR}/v1/affiliations/{aff['id']}/decision", json={"decision": "approve"}, headers=admin))
    offering = check(c.post(f"{PR}/v1/providers/{provider['id']}/services", json={"branch_id": branch["id"], "category": "dermatology", "name": "Dermatology consultation", "duration_minutes": 30, "buffer_minutes": 10, "price_type": "fixed", "professional_fee_minor": 60000, "facility_fee_minor": 15000}, headers=owner), 201)
    for weekday in range(7):
        check(c.post(f"{PR}/v1/providers/{provider['id']}/availability-rules", json={"branch_id": branch["id"], "weekday": weekday, "start": "09:00", "end": "17:00", "effective_from": str(date.today())}, headers=owner), 201)
    return {"owner": owner, "owner_id": owner_id, "admin": admin, "admin_id": admin_id, "provider": provider, "facility": facility, "offering": offering}


def platform_staff(c: httpx.Client) -> dict:
    _, _, email = register(c, "reviewer")
    subprocess.run([PSQL, IDENTITY_DB, "-qtAc", f"INSERT INTO user_roles (user_id, role_id) SELECT id, '{ADMIN_ROLE}' FROM users WHERE identifier = '{email}'"], check=True)
    tokens = check(c.post(f"{ID}/v1/auth/login", json={"identifier": email, "password": PASSWORD}))
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def stored_bytes(record_id: str) -> bytes:
    from pymongo import MongoClient

    db = MongoClient(MONGO_URI)[MONGO_DB]
    meta = db["medical_records"].find_one({"_id": record_id})
    chunks = db["record_files.chunks"].find({"files_id": meta["file"]["storage_key"]}).sort("n", 1)
    return b"".join(bytes(ch["data"]) for ch in chunks)


async def jetstream_events(grant_id: str) -> list[dict]:
    import nats

    nc = await nats.connect(NATS_URL, connect_timeout=2)
    js = nc.jetstream()
    found: list[dict] = []
    sub = await js.subscribe("healuxa.profile.*.v1", ordered_consumer=True, deliver_policy=nats.js.api.DeliverPolicy.ALL)
    try:
        while True:
            msg = await sub.next_msg(timeout=2)
            body = json.loads(msg.data)
            if body["payload"].get("grant_id") == grant_id:
                found.append(body)
    except nats.errors.TimeoutError:
        pass
    finally:
        await nc.close()
    return found


def main() -> None:
    c = httpx.Client(timeout=20)
    staff = platform_staff(c)
    home = practice(c, staff, f"Dr. Records Smoke {uuid.uuid4().hex[:4]}")
    rival = practice(c, staff, f"Dr. Rival {uuid.uuid4().hex[:4]}")
    customer, customer_id, email = register(c, "customer")
    print(f"customer {email}; practice {home['provider']['display_name']} / {home['facility']['name']}")

    # Booking: the natural moment to share.
    start = datetime.now(UTC) + timedelta(days=1)
    slots = check(c.get(f"{AP}/v1/services/{home['offering']['id']}/slots", params={"from": start.date().isoformat(), "to": (start + timedelta(days=3)).date().isoformat()}))["slots"]
    booking = check(c.post(f"{AP}/v1/appointments", json={"service_id": home["offering"]["id"], "scheduled_at": slots[0]["scheduled_at"]}, headers={**customer, **key()}), 201)
    check(c.post(f"{AP}/v1/appointments/{booking['id']}/status", json={"transition": "submit"}, headers=customer))
    print(f"booked {booking['id']} with provider {booking['provider_id']}")

    # Upload: a fake executable is refused by content; a real PDF is accepted and stored encrypted.
    bad = c.post(f"{PF}/v1/records", headers=customer, data={"title": "x", "type": "lab_result"}, files={"file": ("lab.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")})
    assert bad.status_code == 422 and bad.json()["errors"][0]["code"] == "unsupported_type", bad.text
    record = check(c.post(f"{PF}/v1/records", headers={**customer, **key()}, data={"title": SECRET_TITLE, "type": "lab_result", "document_date": "2026-11-01"}, files={"file": ("lipids.pdf", PDF, "application/pdf")}), 201)
    at_rest = stored_bytes(record["id"])
    assert at_rest.startswith(b"HXR1") and b"LDL" not in at_rest and at_rest != PDF
    print(f"uploaded record {record['id']} ({record['size_bytes']} B); stored bytes are ciphertext ({len(at_rest)} B, key id in header)")

    doctor = home["owner"]
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=doctor), 404)
    print("practitioner before any grant → 404")

    grant = check(c.post(f"{PF}/v1/record-grants", headers={**customer, **key()}, json={"grantee_type": "provider", "grantee_id": booking["provider_id"], "record_ids": [record["id"]], "purpose": "consultation", "expires_in_days": 30, "appointment_id": booking["id"]}), 201)
    print(f"shared from booking → grant {grant['id']} until {grant['expires_at'][:10]} ({grant['grantee_name']})")

    shared = check(c.get(f"{PF}/v1/shared-records", params={"grantee_type": "provider", "grantee_id": home["provider"]["id"]}, headers=doctor))["data"]
    assert [g["id"] for g in shared] == [grant["id"]] and shared[0]["appointment_id"] == booking["id"]
    detail = check(c.get(f"{PF}/v1/shared-records/{grant['id']}", headers=doctor))
    assert [r["id"] for r in detail["records"]] == [record["id"]]
    download = check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=doctor))
    assert download.content == PDF
    assert download.headers["content-disposition"].startswith("attachment") and download.headers["x-content-type-options"] == "nosniff"
    print("practitioner (membership verified by provider-service) lists, views and downloads the exact bytes")

    rival_doctor = rival["owner"]
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=rival_doctor), 404)
    assert check(c.get(f"{PF}/v1/shared-records", params={"grantee_type": "provider", "grantee_id": home["provider"]["id"]}, headers=rival_doctor), 403)
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=staff), 404)
    print("other practice's practitioner → 404/403; platform admin → 404 (no implicit access)")

    check(c.post(f"{PF}/v1/record-grants/{grant['id']}/revoke", headers=customer))
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=doctor), 403)
    assert check(c.get(f"{PF}/v1/shared-records", params={"grantee_type": "provider", "grantee_id": home["provider"]["id"]}, headers=doctor))["data"] == []
    print("customer stops sharing → practitioner gets 403 on the next request")

    # Facility staff: allowed while staff, refused once removed (checked live against provider-service).
    nurse, nurse_id, _ = register(c, "scheduler")
    check(c.post(f"{PR}/v1/facilities/{home['facility']['id']}/staff", json={"user_id": nurse_id, "role": "scheduler"}, headers=home["admin"]), 201)
    fgrant = check(c.post(f"{PF}/v1/record-grants", headers={**customer, **key()}, json={"grantee_type": "facility", "grantee_id": home["facility"]["id"], "record_ids": [record["id"]], "purpose": "follow_up", "expires_in_days": 7}), 201)
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=nurse)).content == PDF
    removed = c.delete(f"{PR}/v1/facilities/{home['facility']['id']}/staff/{nurse_id}", headers=home["admin"])
    assert removed.status_code == 204, removed.text
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=nurse), 404)
    print("facility scheduler downloads while on staff; removed from staff → refused immediately")
    check(c.post(f"{PF}/v1/record-grants/{fgrant['id']}/revoke", headers=customer))

    log = check(c.get(f"{PF}/v1/record-access-log", params={"record_id": record["id"], "limit": 100}, headers=customer))["data"]
    seq = [(e["action"], e["actor"]["kind"], e.get("reason")) for e in reversed(log)]
    expected = [
        ("denied", "other", "no_grant"),
        ("grant", "owner", None),
        ("view", "practitioner", None),
        ("download", "practitioner", None),
        ("denied", "other", "not_member"),
        ("denied", "other", "not_member"),
        ("revoke", "owner", None),
        ("denied", "practitioner", "grant_revoked"),
        ("grant", "owner", None),
        ("download", "facility_staff", None),
        ("denied", "other", "not_member"),
        ("revoke", "owner", None),
    ]
    if seq != expected:
        sys.exit("FAIL access log\n got: " + json.dumps(seq) + "\nwant: " + json.dumps(expected))
    print("access log (customer view), oldest first:")
    for e in reversed(log):
        who = (e["organisation"] or {}).get("name") or e["actor"]["kind"]
        print(f"  {e['occurred_at'][11:19]} {e['action']:<8} {e['actor']['kind']:<14} {who:<32} {e.get('reason') or ''}")

    events = asyncio.run(jetstream_events(grant["id"]))
    types = sorted({e["type"] for e in events})
    assert types == ["profile.record_accessed", "profile.record_grant_created", "profile.record_grant_revoked"], types
    blob = json.dumps(events)
    assert SECRET_TITLE not in blob and "lipids" not in blob and "LDL" not in blob
    print(f"JetStream: {len(events)} event(s) for the grant {types}; payloads carry ids only")

    check(c.delete(f"{PF}/v1/records/{record['id']}", headers=customer), 204)
    assert check(c.get(f"{PF}/v1/records/{record['id']}/content", headers=customer), 404)
    print("customer deletes the record → bytes gone")
    print("PASS records end to end")


if __name__ == "__main__":
    main()
