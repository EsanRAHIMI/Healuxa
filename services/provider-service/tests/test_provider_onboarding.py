"""Provider onboarding, credential review and activation rules."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient
from ulid import ULID

from helpers import create_provider, new_user, ok, outbox_events, staff, user, verify_provider


async def test_application_starts_pending_and_unverified(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    assert provider["status"] == "pending"
    assert provider["verification_status"] == "unverified"
    assert provider["user_id"] == owner
    assert provider["specialties"] == ["infectious diseases"]
    me = await ok(await client.get("/v1/providers/me", headers=user(owner)))
    assert me["id"] == provider["id"]


async def test_one_profile_per_account_and_idempotent_replay(client: AsyncClient) -> None:
    owner = new_user()
    headers = {**user(owner), "Idempotency-Key": "onboard-1"}
    first = await ok(await client.post("/v1/providers", json={"type": "doctor", "display_name": "Dr. A", "specialties": ["x"], "languages": ["en"]}, headers=headers), 201)
    replay = await ok(await client.post("/v1/providers", json={"type": "doctor", "display_name": "Dr. A", "specialties": ["x"], "languages": ["en"]}, headers=headers), 201)
    assert replay["id"] == first["id"]
    again = await client.post("/v1/providers", json={"type": "doctor", "display_name": "Dr. A", "specialties": ["x"], "languages": ["en"]}, headers=user(owner))
    assert again.status_code == 409


async def test_verified_license_required_for_activation(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    reviewer = staff()
    blocked = await client.post(
        f"/v1/providers/{provider['id']}/status", json={"status": "active", "reason": "go live"}, headers=reviewer
    )
    assert blocked.status_code == 422

    await verify_provider(client, provider["id"], owner)
    current = await ok(await client.get(f"/v1/providers/{provider['id']}", headers=user(owner)))
    assert current["status"] == "active"
    assert current["verification_status"] == "verified"
    assert [c["issuing_authority"] for c in current["verified_credentials"]] == ["DHA"]


async def test_expired_credential_cannot_be_verified(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    credential = await ok(
        await client.post(
            f"/v1/providers/{provider['id']}/credentials",
            json={
                "kind": "professional_license",
                "issuing_authority": "DHA",
                "number": "OLD-1",
                "valid_until": str(date.today() - timedelta(days=1)),
            },
            headers=user(owner),
        ),
        201,
    )
    response = await client.post(
        f"/v1/providers/{provider['id']}/credentials/{credential['id']}/review",
        json={"decision": "verify"},
        headers=staff(),
    )
    assert response.status_code == 422


async def test_rejection_requires_note_and_is_final(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    credential = await ok(
        await client.post(
            f"/v1/providers/{provider['id']}/credentials",
            json={"kind": "professional_license", "issuing_authority": "DHA", "number": "N-1"},
            headers=user(owner),
        ),
        201,
    )
    url = f"/v1/providers/{provider['id']}/credentials/{credential['id']}/review"
    assert (await client.post(url, json={"decision": "reject"}, headers=staff())).status_code == 422
    rejected = await ok(await client.post(url, json={"decision": "reject", "note": "Number not found in DHA registry"}, headers=staff()))
    assert rejected["status"] == "rejected"
    assert (await client.post(url, json={"decision": "verify"}, headers=staff())).status_code == 409
    state = await ok(await client.get(f"/v1/providers/{provider['id']}", headers=user(owner)))
    assert state["verification_status"] == "rejected"


async def test_only_staff_review_and_change_status(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    credential = await ok(
        await client.post(
            f"/v1/providers/{provider['id']}/credentials",
            json={"kind": "professional_license", "issuing_authority": "DHA", "number": "N-2"},
            headers=user(owner),
        ),
        201,
    )
    review = await client.post(
        f"/v1/providers/{provider['id']}/credentials/{credential['id']}/review",
        json={"decision": "verify"},
        headers=user(owner),
    )
    assert review.status_code == 403  # missing providers:verify permission
    status = await client.post(
        f"/v1/providers/{provider['id']}/status", json={"status": "active", "reason": "self"}, headers=user(owner)
    )
    assert status.status_code == 403


async def test_other_users_cannot_manage_provider(client: AsyncClient) -> None:
    provider = await create_provider(client, new_user())
    intruder = user(new_user())
    assert (await client.patch(f"/v1/providers/{provider['id']}", json={"title": "x"}, headers=intruder)).status_code == 404
    assert (await client.get(f"/v1/providers/{provider['id']}/credentials", headers=intruder)).status_code == 404


async def test_identity_change_on_verified_profile_requires_re_review(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    await verify_provider(client, provider["id"], owner)
    updated = await ok(
        await client.patch(f"/v1/providers/{provider['id']}", json={"display_name": "Dr. Someone Else"}, headers=user(owner))
    )
    assert updated["verification_status"] == "under_review"
    public = await client.get(f"/v1/providers/{provider['id']}")
    assert public.status_code == 404  # hidden from the directory until re-verified


async def test_if_match_guards_concurrent_edits(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    stale = await client.patch(
        f"/v1/providers/{provider['id']}", json={"title": "x"}, headers={**user(owner), "If-Match": '"v99"'}
    )
    assert stale.status_code == 409


async def test_status_events_are_staged(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    await verify_provider(client, provider["id"], owner)
    events = [e for e in await outbox_events("catalog.provider_status_changed") if e["payload"]["provider_id"] == provider["id"]]
    assert [e["payload"]["status"] for e in events][-1] == "active"
    assert events[-1]["payload"]["verification_status"] == "verified"
    assert all("number" not in e["payload"] for e in events)


async def test_unknown_language_tag_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/providers",
        json={"type": "doctor", "display_name": "Dr. B", "specialties": ["x"], "languages": ["en"], "bio": {"xx": "?"}},
        headers=user(str(ULID())),
    )
    assert response.status_code == 422
