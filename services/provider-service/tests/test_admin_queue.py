"""Staff-only verification queues: permission-gated, tenant-scoped, FIFO cursor pagination."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient
from ulid import ULID

from provider_service.api.deps import principal_headers

from helpers import FACILITY_BODY, create_provider, new_user, ok, staff, user


def provider_reviewer(*, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(str(ULID()), permissions="providers:onboard,providers:verify", tenant_id=tenant_id)


def facility_reviewer(*, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(str(ULID()), permissions="facilities:onboard,facilities:verify", tenant_id=tenant_id)


async def submit_license(client: AsyncClient, provider_id: str, owner: str) -> dict:
    return await ok(
        await client.post(
            f"/v1/providers/{provider_id}/credentials",
            json={
                "kind": "professional_license",
                "issuing_authority": "dha",
                "number": f"DHA-{ULID()}",
                "valid_until": str(date.today() + timedelta(days=365)),
            },
            headers=user(owner),
        ),
        201,
    )


async def test_queues_require_staff_permissions(client: AsyncClient) -> None:
    regular = user(new_user())
    for path in ("/v1/admin/providers", "/v1/admin/credentials", "/v1/admin/facilities"):
        assert (await client.get(path, headers=regular)).status_code == 403, path
        assert (await client.get(path)).status_code == 401, path
    # Each queue needs its own verify permission.
    assert (await client.get("/v1/admin/facilities", headers=provider_reviewer())).status_code == 403
    assert (await client.get("/v1/admin/credentials", headers=facility_reviewer())).status_code == 403
    assert (await client.get("/v1/admin/providers", headers=facility_reviewer())).status_code == 403


async def test_credential_queue_lists_submitted_fifo_and_drains_on_review(client: AsyncClient) -> None:
    owners = [new_user(), new_user()]
    providers = [await create_provider(client, o, display_name=f"Dr. Queue {i}") for i, o in enumerate(owners)]
    first = await submit_license(client, providers[0]["id"], owners[0])
    second = await submit_license(client, providers[1]["id"], owners[1])

    reviewer = provider_reviewer()
    queue = await ok(await client.get("/v1/admin/credentials", headers=reviewer))
    assert [c["id"] for c in queue["data"]] == [first["id"], second["id"]]
    assert queue["data"][0]["number"] == first["number"]  # staff see the number to check the registry
    assert queue["data"][0]["submitted_at"]
    assert queue["page"] == {"next_cursor": None, "limit": 20, "has_more": False}

    page1 = await ok(await client.get("/v1/admin/credentials", params={"limit": 1}, headers=reviewer))
    assert [c["id"] for c in page1["data"]] == [first["id"]]
    assert page1["page"]["has_more"] is True
    page2 = await ok(
        await client.get(
            "/v1/admin/credentials", params={"limit": 1, "cursor": page1["page"]["next_cursor"]}, headers=reviewer
        )
    )
    assert [c["id"] for c in page2["data"]] == [second["id"]]
    assert page2["page"]["has_more"] is False

    await ok(
        await client.post(
            f"/v1/providers/{providers[0]['id']}/credentials/{first['id']}/review",
            json={"decision": "verify"},
            headers=reviewer,
        )
    )
    remaining = await ok(await client.get("/v1/admin/credentials", headers=reviewer))
    assert [c["id"] for c in remaining["data"]] == [second["id"]]
    verified = await ok(await client.get("/v1/admin/credentials", params={"status": "verified"}, headers=reviewer))
    assert [c["id"] for c in verified["data"]] == [first["id"]]
    by_provider = await ok(
        await client.get(
            "/v1/admin/credentials", params={"provider_id": providers[1]["id"], "status": "submitted"}, headers=reviewer
        )
    )
    assert [c["id"] for c in by_provider["data"]] == [second["id"]]


async def test_provider_queue_filters_and_returns_private_view(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    untouched = await create_provider(client, new_user(), display_name="Dr. Untouched")
    await submit_license(client, provider["id"], owner)

    reviewer = provider_reviewer()
    under_review = await ok(
        await client.get("/v1/admin/providers", params={"verification_status": "under_review"}, headers=reviewer)
    )
    assert [p["id"] for p in under_review["data"]] == [provider["id"]]
    assert under_review["data"][0]["user_id"] == owner
    pending = await ok(await client.get("/v1/admin/providers", params={"status": "pending"}, headers=reviewer))
    assert {p["id"] for p in pending["data"]} == {provider["id"], untouched["id"]}
    assert (await client.get("/v1/admin/providers", params={"status": "bogus"}, headers=reviewer)).status_code == 422


async def test_facility_queue_lists_under_review_and_hides_reviewed(client: AsyncClient) -> None:
    admin = new_user()
    facility = await ok(
        await client.post("/v1/facilities", json={**FACILITY_BODY, "license_number": f"FAC-{ULID()}"}, headers=user(admin)),
        201,
    )
    reviewer = facility_reviewer()
    queue = await ok(
        await client.get("/v1/admin/facilities", params={"verification_status": "under_review"}, headers=reviewer)
    )
    assert [f["id"] for f in queue["data"]] == [facility["id"]]
    assert queue["data"][0]["license_number"] == facility["license_number"]

    await ok(await client.post(f"/v1/facilities/{facility['id']}/review", json={"decision": "verify"}, headers=staff()))
    after = await ok(
        await client.get("/v1/admin/facilities", params={"verification_status": "under_review"}, headers=reviewer)
    )
    assert after["data"] == []


async def test_queues_are_tenant_scoped(client: AsyncClient) -> None:
    owner = new_user()
    provider = await create_provider(client, owner)
    await submit_license(client, provider["id"], owner)
    await ok(
        await client.post("/v1/facilities", json={**FACILITY_BODY, "license_number": f"FAC-{ULID()}"}, headers=user(new_user())),
        201,
    )
    europe = principal_headers(
        str(ULID()), permissions="providers:verify,facilities:verify", tenant_id="healuxa-europe"
    )
    for path in ("/v1/admin/providers", "/v1/admin/credentials", "/v1/admin/facilities"):
        assert (await ok(await client.get(path, headers=europe)))["data"] == [], path


async def test_malformed_cursor_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/v1/admin/providers", params={"cursor": "not-a-cursor"}, headers=provider_reviewer())
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
