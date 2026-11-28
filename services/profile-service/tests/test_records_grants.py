"""Consent grants: lifecycle, default deny, cross-organisation / cross-tenant isolation, access log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from profile_service.config import settings
from profile_service.infra.mongo import get_database
from records_helpers import PDF, PNG, access_log, customer, grant, new_id, ok, platform_admin, practice, uploaded

pytestmark = pytest.mark.mongo


async def _setup(client: AsyncClient, directory) -> dict:
    owner, doctor = new_id(), new_id()
    provider_id = directory.add_provider(doctor)
    record = await uploaded(client, customer(owner))
    other = await uploaded(client, customer(owner), data=PNG, filename="scan.png", content_type="image/png", record_type="imaging_report")
    return {"owner": owner, "doctor": doctor, "provider_id": provider_id, "record": record, "other": other}


async def _download(client: AsyncClient, headers: dict, record_id: str):
    return await client.get(f"/v1/records/{record_id}/content", headers=headers)


async def test_grant_lifecycle_active_then_revoked_is_denied_immediately(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    created = await ok(
        await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]),
        201,
    )
    assert created["status"] == "active" and created["grantee_name"] == "Dr. Sara Haddad"
    expires = datetime.fromisoformat(created["expires_at"])
    assert timedelta(days=29, hours=23) < expires - datetime.now(UTC) <= timedelta(days=30)

    # The shared record shows who it is shared with.
    mine = await ok(await client.get(f"/v1/records/{rid}", headers=customer(s["owner"])))
    assert [sh["grantee_id"] for sh in mine["shares"]] == [s["provider_id"]]

    shared = await ok(
        await client.get(
            "/v1/shared-records",
            params={"grantee_type": "provider", "grantee_id": s["provider_id"]},
            headers=practice(s["doctor"]),
        )
    )
    assert [g["id"] for g in shared["data"]] == [created["id"]]
    assert shared["data"][0]["patient_user_id"] == s["owner"] and shared["data"][0]["record_count"] == 1
    detail = await ok(await client.get(f"/v1/shared-records/{created['id']}", headers=practice(s["doctor"])))
    assert [r["id"] for r in detail["records"]] == [rid]

    allowed = await _download(client, practice(s["doctor"]), rid)
    assert allowed.status_code == 200 and allowed.content == PDF
    assert allowed.headers["content-disposition"].startswith("attachment")
    # A record not in the grant stays private.
    assert (await _download(client, practice(s["doctor"]), s["other"]["id"])).status_code == 404

    revoked = await ok(await client.post(f"/v1/record-grants/{created['id']}/revoke", headers=customer(s["owner"])))
    assert revoked["status"] == "revoked" and revoked["revoked_at"]
    denied = await _download(client, practice(s["doctor"]), rid)
    assert denied.status_code == 403 and PDF not in denied.content
    assert (await client.get(f"/v1/shared-records/{created['id']}", headers=practice(s["doctor"]))).status_code == 403
    after = await ok(
        await client.get(
            "/v1/shared-records", params={"grantee_type": "provider", "grantee_id": s["provider_id"]}, headers=practice(s["doctor"])
        )
    )
    assert after["data"] == []
    assert (await ok(await client.get(f"/v1/records/{rid}", headers=customer(s["owner"]))))["shares"] == []
    # Revoking twice is harmless.
    assert (await ok(await client.post(f"/v1/record-grants/{created['id']}/revoke", headers=customer(s["owner"]))))["status"] == "revoked"

    log = await access_log(s["owner"])
    by_record = [(e["action"], e.get("attempted"), e.get("reason")) for e in log if e["record_id"] == rid]
    assert by_record == [
        ("grant", None, None),
        ("view", None, None),
        ("download", None, None),
        ("revoke", None, None),
        ("denied", "download", "grant_revoked"),
        ("denied", "view", "grant_revoked"),
    ]
    # The refused attempt on the record outside the grant is logged too.
    assert [(e["action"], e["reason"]) for e in log if e["record_id"] == s["other"]["id"]] == [("denied", "no_grant")]
    view = next(e for e in log if e["action"] == "download" and e["actor_user_id"] == s["doctor"])
    assert view["actor_kind"] == "practitioner"
    assert view["organisation"] == {"type": "provider", "id": s["provider_id"], "name": "Dr. Sara Haddad"}
    assert view["client"]["agent"] is not None


async def test_customer_sees_who_accessed_what(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    g = await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    await _download(client, {**practice(s["doctor"]), "User-Agent": "Mozilla/5.0 (Macintosh; Mac OS X 14) Chrome/130 Safari/537", "X-Forwarded-For": "203.0.113.77"}, rid)
    page = await ok(await client.get("/v1/record-access-log", params={"record_id": rid}, headers=customer(s["owner"])))
    actions = [e["action"] for e in page["data"]]
    assert actions == ["download", "grant"]  # newest first
    entry = page["data"][0]
    assert entry["actor"] == {"kind": "practitioner", "user_id": s["doctor"]}
    assert entry["organisation"]["name"] == "Dr. Sara Haddad" and entry["grant_id"] == g["id"]
    assert entry["client"] == {"network": "203.0.113.0/24", "agent": "Chrome on macOS"}
    # Pagination.
    first = await ok(await client.get("/v1/record-access-log", params={"limit": 1}, headers=customer(s["owner"])))
    assert first["page"]["has_more"] and len(first["data"]) == 1
    second = await ok(
        await client.get("/v1/record-access-log", params={"limit": 1, "cursor": first["page"]["next_cursor"]}, headers=customer(s["owner"]))
    )
    assert second["data"][0]["id"] != first["data"][0]["id"]
    # Nobody else can read the owner's log.
    assert (await ok(await client.get("/v1/record-access-log", headers=customer(s["doctor"]))))["data"] == []


async def test_expired_grant_is_denied(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    g = await ok(
        await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid], expires_in_days=7),
        201,
    )
    assert (await _download(client, practice(s["doctor"]), rid)).status_code == 200
    await get_database()["record_grants"].update_one({"_id": g["id"]}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    denied = await _download(client, practice(s["doctor"]), rid)
    assert denied.status_code == 403
    listed = await ok(await client.get("/v1/record-grants", params={"record_id": rid}, headers=customer(s["owner"])))
    assert listed["data"][0]["status"] == "expired"
    assert (await access_log(s["owner"]))[-1]["reason"] == "grant_expired"


async def test_expiry_choices_are_bounded(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    too_long = await grant(
        client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"],
        record_ids=[s["record"]["id"]], expires_in_days=settings.records_max_grant_days + 1,
    )
    assert too_long.status_code == 422
    zero = await grant(
        client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[s["record"]["id"]], expires_in_days=0
    )
    assert zero.status_code == 422


async def test_default_deny_without_grant_and_for_platform_admins(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    # The practitioner has no grant at all.
    assert (await _download(client, practice(s["doctor"]), rid)).status_code == 404
    # A platform admin holding every permission still has no implicit access.
    admin = new_id()
    assert (await _download(client, platform_admin(admin), rid)).status_code == 404
    assert (await client.get(f"/v1/records/{rid}", headers=platform_admin(admin))).status_code == 404
    reasons = [e["reason"] for e in await access_log(s["owner"]) if e["action"] == "denied"]
    assert reasons == ["no_grant", "no_grant"]


async def test_cross_organisation_access_is_denied(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    g = await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    rival_doctor = new_id()
    rival_provider = directory.add_provider(rival_doctor, name="Dr. Other")
    clinic = directory.add_facility()
    directory.add_staff(clinic, rival_doctor, "facility_admin")
    # A member of other organisations cannot read the record, list it, or open the grant.
    assert (await _download(client, practice(rival_doctor), rid)).status_code == 404
    assert (await client.get(f"/v1/shared-records/{g['id']}", headers=practice(rival_doctor))).status_code == 404
    for gtype, gid in (("provider", s["provider_id"]), ("provider", rival_provider), ("facility", clinic)):
        response = await client.get("/v1/shared-records", params={"grantee_type": gtype, "grantee_id": gid}, headers=practice(rival_doctor))
        if gid == s["provider_id"]:
            assert response.status_code == 403  # not a member of the granted practice
        else:
            assert (await ok(response))["data"] == []
    # Claiming membership in a header changes nothing: membership comes from provider-service only.
    forged = {**practice(rival_doctor), "X-Healuxa-Provider": s["provider_id"], "X-Healuxa-Roles": "provider"}
    assert (await _download(client, forged, rid)).status_code == 404


async def test_cross_tenant_access_is_denied(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    g = await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    # Same practitioner user, other tenant (and a directory that would say yes there).
    directory.providers[s["provider_id"]]["tenant"] = "other-tenant"
    other = practice(s["doctor"], tenant_id="other-tenant")
    assert (await _download(client, other, rid)).status_code == 404
    assert (await client.get(f"/v1/shared-records/{g['id']}", headers=other)).status_code == 404
    listed = await ok(
        await client.get("/v1/shared-records", params={"grantee_type": "provider", "grantee_id": s["provider_id"]}, headers=other)
    )
    assert listed["data"] == []
    # A customer cannot share another tenant's grantee or another customer's record.
    directory.providers[s["provider_id"]]["tenant"] = "healuxa-dubai"
    foreign = directory.add_provider(new_id(), tenant_id="other-tenant")
    bad = await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=foreign, record_ids=[rid])
    assert bad.status_code == 422 and bad.json()["errors"][0]["code"] == "unknown_grantee"
    stranger_record = await uploaded(client, customer(new_id()))
    stolen = await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[stranger_record["id"]])
    assert stolen.status_code == 422 and stolen.json()["errors"][0]["code"] == "unknown_record"


async def test_facility_grant_requires_current_staff_membership(client: AsyncClient, directory) -> None:
    owner, nurse, biller = new_id(), new_id(), new_id()
    clinic = directory.add_facility()
    directory.add_staff(clinic, nurse, "scheduler")
    directory.add_staff(clinic, biller, "billing")
    record = await uploaded(client, customer(owner))
    g = await ok(await grant(client, customer(owner), grantee_type="facility", grantee_id=clinic, record_ids=[record["id"]]), 201)
    assert (await _download(client, practice(nurse), record["id"])).status_code == 200
    # Billing staff are members but not allowed to read clinical documents.
    assert (await _download(client, practice(biller), record["id"])).status_code == 404
    # Removed from staff: the next request is refused, the grant itself is unchanged.
    calls = directory.actor_calls
    directory.remove_staff(clinic, nurse)
    assert (await _download(client, practice(nurse), record["id"])).status_code == 404
    assert directory.actor_calls == calls + 1  # membership is checked on every read, never cached
    assert (await client.get(f"/v1/shared-records/{g['id']}", headers=practice(nurse))).status_code == 404
    # A suspended facility loses access too.
    directory.add_staff(clinic, nurse, "facility_admin")
    directory.facilities[clinic]["status"] = "suspended"
    assert (await _download(client, practice(nurse), record["id"])).status_code == 404


async def test_read_shared_permission_is_required(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    no_perm = customer(s["doctor"])  # records:manage only
    assert (await _download(client, no_perm, rid)).status_code == 404
    assert (
        await client.get("/v1/shared-records", params={"grantee_type": "provider", "grantee_id": s["provider_id"]}, headers=no_perm)
    ).status_code == 403
    assert (await access_log(s["owner"]))[-1]["reason"] == "missing_permission"


async def test_directory_outage_fails_closed_and_is_logged(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    directory.down = True
    response = await _download(client, practice(s["doctor"]), rid)
    assert response.status_code == 503 and PDF not in response.content
    assert (await access_log(s["owner"]))[-1]["reason"] == "verification_unavailable"
    # Owners still reach their own files without provider-service.
    assert (await _download(client, customer(s["owner"]), rid)).status_code == 200
    # New grants cannot be validated, so they are refused.
    blocked = await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid])
    assert blocked.status_code == 503


async def test_partial_revoke_and_regrant_supersedes(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    a, b = s["record"]["id"], s["other"]["id"]
    g = await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[a, b]), 201)
    partial = await ok(await client.post(f"/v1/record-grants/{g['id']}/revoke", headers=customer(s["owner"]), json={"record_ids": [b]}))
    assert partial["status"] == "active" and partial["record_ids"] == [a]
    assert (await _download(client, practice(s["doctor"]), a)).status_code == 200
    assert (await _download(client, practice(s["doctor"]), b)).status_code == 403
    # Sharing a again replaces the old grant (one active grant per record and organisation).
    newer = await ok(
        await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[a], expires_in_days=90),
        201,
    )
    old = await ok(await client.get("/v1/record-grants", headers=customer(s["owner"])))
    statuses = {x["id"]: x["status"] for x in old["data"]}
    assert statuses == {newer["id"]: "active", g["id"]: "revoked"}
    mine = await ok(await client.get(f"/v1/records/{a}", headers=customer(s["owner"])))
    assert [sh["grant_id"] for sh in mine["shares"]] == [newer["id"]]


async def test_deleting_a_shared_record_ends_access(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    rid = s["record"]["id"]
    g = await ok(await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[rid]), 201)
    assert (await client.delete(f"/v1/records/{rid}", headers=customer(s["owner"]))).status_code == 204
    assert (await _download(client, practice(s["doctor"]), rid)).status_code == 404
    listed = await ok(await client.get("/v1/record-grants", headers=customer(s["owner"])))
    assert listed["data"][0]["id"] == g["id"] and listed["data"][0]["status"] == "revoked"


async def test_only_the_owner_manages_grants(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    g = await ok(
        await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[s["record"]["id"]]),
        201,
    )
    for headers in (practice(s["doctor"]), platform_admin(new_id())):
        assert (await client.post(f"/v1/record-grants/{g['id']}/revoke", headers=headers)).status_code == 404
        assert (await ok(await client.get("/v1/record-grants", headers=headers)))["data"] == []
    # The doctor cannot re-share the patient's record onward.
    other_provider = directory.add_provider(new_id())
    onward = await grant(client, customer(s["doctor"]), grantee_type="provider", grantee_id=other_provider, record_ids=[s["record"]["id"]])
    assert onward.status_code == 422
    # A customer cannot grant to themselves-as-grantee to bypass ownership: their own read is the owner path.
    assert (await client.get(f"/v1/shared-records/{g['id']}", headers=practice(s["owner"]))).status_code == 404


async def test_grant_idempotency_and_appointment_link(client: AsyncClient, directory) -> None:
    s = await _setup(client, directory)
    appt = new_id()
    keyed = {**customer(s["owner"]), "Idempotency-Key": "grant-key-00001"}
    body = {"grantee_type": "provider", "grantee_id": s["provider_id"], "record_ids": [s["record"]["id"]], "appointment_id": appt}
    first = await ok(await grant(client, keyed, **body), 201)
    again = await ok(await grant(client, keyed, **body), 201)
    assert again["id"] == first["id"] and first["appointment_id"] == appt
    assert await get_database()["record_grants"].count_documents({}) == 1
    conflict = await grant(client, keyed, **{**body, "purpose": "treatment"})
    assert conflict.status_code == 409 and conflict.json()["code"] == "idempotency_conflict"
    shared = await ok(
        await client.get("/v1/shared-records", params={"grantee_type": "provider", "grantee_id": s["provider_id"]}, headers=practice(s["doctor"]))
    )
    assert shared["data"][0]["appointment_id"] == appt
    dupes = await grant(client, customer(s["owner"]), grantee_type="provider", grantee_id=s["provider_id"], record_ids=[s["record"]["id"]] * 2)
    assert dupes.status_code == 422
