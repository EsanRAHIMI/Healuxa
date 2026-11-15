"""Service-authenticated membership facts profile-service uses to authorise shared-record reads."""

from __future__ import annotations

from httpx import AsyncClient
from ulid import ULID

from helpers import new_user, ok, practice, user
from provider_service.api.deps import principal_headers
from provider_service.config import settings


def service() -> dict[str, str]:
    return principal_headers("profile-service", permissions="service")


def _tenant(tenant_id: str | None = None) -> dict[str, str]:
    return {"tenant_id": tenant_id or settings.tenant_default}


async def test_actor_lists_owned_providers_and_staffed_facilities(client: AsyncClient) -> None:
    setup = await practice(client)
    owner = await ok(
        await client.get(f"/v1/internal/records-access/actors/{setup['owner']}", params=_tenant(), headers=service())
    )
    assert owner["providers"] == [
        {"id": setup["provider"]["id"], "status": "active", "verification_status": "verified"}
    ]
    assert owner["facilities"] == []

    admin = await ok(
        await client.get(f"/v1/internal/records-access/actors/{setup['admin']}", params=_tenant(), headers=service())
    )
    assert admin["providers"] == []
    assert admin["facilities"] == [
        {"id": setup["facility"]["id"], "role": "facility_admin", "status": "active", "verification_status": "verified"}
    ]


async def test_actor_reflects_staff_removal_immediately(client: AsyncClient) -> None:
    setup = await practice(client)
    member = new_user()
    facility_id = setup["facility"]["id"]
    await ok(
        await client.post(
            f"/v1/facilities/{facility_id}/staff", json={"user_id": member, "role": "scheduler"}, headers=user(setup["admin"])
        ),
        201,
    )
    before = await ok(
        await client.get(f"/v1/internal/records-access/actors/{member}", params=_tenant(), headers=service())
    )
    assert [f["role"] for f in before["facilities"]] == ["scheduler"]

    removed = await client.delete(f"/v1/facilities/{facility_id}/staff/{member}", headers=user(setup["admin"]))
    assert removed.status_code == 204, removed.text
    after = await ok(
        await client.get(f"/v1/internal/records-access/actors/{member}", params=_tenant(), headers=service())
    )
    assert after["facilities"] == []


async def test_actor_is_tenant_scoped_and_unknown_user_is_empty(client: AsyncClient) -> None:
    setup = await practice(client)
    other_tenant = await ok(
        await client.get(
            f"/v1/internal/records-access/actors/{setup['owner']}", params=_tenant("other-tenant"), headers=service()
        )
    )
    assert other_tenant == {"user_id": setup["owner"], "providers": [], "facilities": []}
    stranger = str(ULID())
    unknown = await ok(
        await client.get(f"/v1/internal/records-access/actors/{stranger}", params=_tenant(), headers=service())
    )
    assert unknown == {"user_id": stranger, "providers": [], "facilities": []}


async def test_grantee_lookup_returns_public_name_and_is_tenant_scoped(client: AsyncClient) -> None:
    setup = await practice(client)
    provider = await ok(
        await client.get(
            f"/v1/internal/records-access/grantees/provider/{setup['provider']['id']}", params=_tenant(), headers=service()
        )
    )
    assert provider == {
        "type": "provider",
        "id": setup["provider"]["id"],
        "name": setup["provider"]["display_name"],
        "status": "active",
        "verification_status": "verified",
    }
    facility = await ok(
        await client.get(
            f"/v1/internal/records-access/grantees/facility/{setup['facility']['id']}", params=_tenant(), headers=service()
        )
    )
    assert facility["name"] == setup["facility"]["name"] and facility["type"] == "facility"

    for path, params in (
        (f"grantees/provider/{setup['provider']['id']}", _tenant("other-tenant")),
        (f"grantees/facility/{setup['provider']['id']}", _tenant()),
        (f"grantees/provider/{ULID()}", _tenant()),
    ):
        missing = await client.get(f"/v1/internal/records-access/{path}", params=params, headers=service())
        assert missing.status_code == 404, missing.text


async def test_records_access_requires_service_credentials(client: AsyncClient) -> None:
    setup = await practice(client)
    for path in (f"actors/{setup['owner']}", f"grantees/provider/{setup['provider']['id']}"):
        as_user = await client.get(f"/v1/internal/records-access/{path}", params=_tenant(), headers=user(setup["owner"]))
        assert as_user.status_code == 403
        anonymous = await client.get(f"/v1/internal/records-access/{path}", params=_tenant())
        assert anonymous.status_code == 401
