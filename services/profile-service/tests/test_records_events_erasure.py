"""Outbox events (identifiers only, schema-valid) and right-to-erasure for medical records."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from profile_service.consumers.user_deleted import handle_user_deleted
from profile_service.infra.mongo import get_database
from records_helpers import access_log, customer, event_validator, grant, new_id, ok, outbox, practice, uploaded

pytestmark = pytest.mark.mongo

SECRET_TITLE = "HIV viral load result"
SECRET_NOTE = "private clinical note"


async def _shared(client: AsyncClient, directory) -> dict:
    owner, doctor = new_id(), new_id()
    provider_id = directory.add_provider(doctor)
    record = await uploaded(client, customer(owner), title=SECRET_TITLE, filename="viral-load.pdf", extra={"note": SECRET_NOTE})
    appointment = new_id()
    g = await ok(
        await grant(
            client, customer(owner), grantee_type="provider", grantee_id=provider_id, record_ids=[record["id"]], appointment_id=appointment
        ),
        201,
    )
    return {"owner": owner, "doctor": doctor, "provider_id": provider_id, "record": record, "grant": g, "appointment": appointment}


async def test_events_validate_against_schemas_and_carry_ids_only(client: AsyncClient, directory) -> None:
    s = await _shared(client, directory)
    await client.get(f"/v1/records/{s['record']['id']}/content", headers=practice(s["doctor"]))
    await client.get(f"/v1/shared-records/{s['grant']['id']}", headers=practice(s["doctor"]))
    await client.post(f"/v1/record-grants/{s['grant']['id']}/revoke", headers=customer(s["owner"]))
    # The owner's own reads are not published.
    await client.get(f"/v1/records/{s['record']['id']}/content", headers=customer(s["owner"]))

    [created] = await outbox("profile.record_grant_created")
    accessed = await outbox("profile.record_accessed")
    [revoked] = await outbox("profile.record_grant_revoked")
    assert [e["payload"]["action"] for e in accessed] == ["download", "view"]
    for envelope, def_name in [(created, "ProfileRecordGrantCreated"), (revoked, "ProfileRecordGrantRevoked")] + [
        (e, "ProfileRecordAccessed") for e in accessed
    ]:
        errors = list(event_validator(def_name).iter_errors(envelope["payload"]))
        assert not errors, [e.message for e in errors]
        assert envelope["producer"] == "profile-service" and envelope["schema_ref"].endswith(def_name)
        assert envelope["version"] == 1 and envelope["tenant_id"] == "healuxa-dubai"
        text = json.dumps(envelope)
        for secret in (SECRET_TITLE, SECRET_NOTE, "viral-load", "Dr. Sara Haddad", "Haemoglobin"):
            assert secret not in text, secret
    assert created["payload"]["appointment_id"] == s["appointment"]
    assert revoked["payload"] == {
        "grant_id": s["grant"]["id"],
        "user_id": s["owner"],
        "grantee_type": "provider",
        "grantee_id": s["provider_id"],
        "record_ids": [s["record"]["id"]],
        "fully_revoked": True,
        "reason": "owner_revoked",
        "revoked_at": revoked["payload"]["revoked_at"],
    }
    assert accessed[0]["payload"]["accessor_user_id"] == s["doctor"]


async def test_refused_grant_stages_no_event(client: AsyncClient, directory) -> None:
    owner = new_id()
    record = await uploaded(client, customer(owner))
    bad = await grant(client, customer(owner), grantee_type="provider", grantee_id=new_id(), record_ids=[record["id"]])
    assert bad.status_code == 422
    assert await outbox("profile.record_grant_created") == []


async def test_user_deleted_erases_records_bytes_grants_and_history(client: AsyncClient, directory) -> None:
    s = await _shared(client, directory)
    await client.get(f"/v1/records/{s['record']['id']}/content", headers=practice(s["doctor"]))
    # The doctor is also a customer with their own record, read by someone else; deleting the patient
    # must not touch it, and deleting the doctor later keeps that patient's history (anonymised).
    other_owner = new_id()
    other_record = await uploaded(client, customer(other_owner))
    keep_grant = await ok(
        await grant(client, customer(other_owner), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[other_record["id"]]),
        201,
    )
    await client.get(f"/v1/records/{other_record['id']}/content", headers=practice(s["doctor"]))
    db = get_database()
    files_before = await db["record_files.files"].count_documents({})
    assert files_before == 2

    envelope = {"tenant_id": "healuxa-dubai", "payload": {"user_id": s["owner"]}}
    await handle_user_deleted(envelope)
    await handle_user_deleted(envelope)  # redelivery is harmless

    assert await db["medical_records"].count_documents({"user_id": s["owner"]}) == 0
    assert await db["record_grants"].count_documents({"user_id": s["owner"]}) == 0
    assert await access_log(s["owner"]) == []
    assert await db["record_files.files"].count_documents({}) == 1
    assert await db["record_blob_gc"].count_documents({}) == 0
    assert (await client.get(f"/v1/records/{s['record']['id']}/content", headers=practice(s["doctor"]))).status_code == 404
    # Unrelated customer untouched.
    assert await db["medical_records"].count_documents({"user_id": other_owner}) == 1
    assert await db["record_grants"].count_documents({"_id": keep_grant["id"]}) == 1

    # Erasing the accessor keeps the owner's history but drops the accessor's user id.
    await handle_user_deleted({"tenant_id": "healuxa-dubai", "payload": {"user_id": s["doctor"]}})
    history = await access_log(other_owner)
    reads = [e for e in history if e["action"] == "download"]
    assert reads and all(e["actor_user_id"] is None for e in reads)
    assert reads[0]["organisation"]["id"] == s["provider_id"]


async def test_user_deleted_requires_ids(client: AsyncClient) -> None:
    with pytest.raises(ValueError):
        await handle_user_deleted({"tenant_id": "healuxa-dubai", "payload": {}})
