"""records RBAC (migration 0011): every account manages its own records and may read records shared with
an organisation it belongs to; profile-service still requires an active grant and live membership."""

from __future__ import annotations

from sqlalchemy import select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role

RECORDS = {"records:manage", "records:read_shared"}


async def _permissions(role_name: str) -> set[str]:
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == role_name))
    assert role is not None
    return set(role.permissions or [])


async def test_user_and_admin_roles_have_records_permissions() -> None:
    assert RECORDS <= await _permissions("user")
    assert RECORDS <= await _permissions("admin")


async def test_finance_role_gets_no_records_access() -> None:
    assert not RECORDS & await _permissions("finance")


async def test_new_account_token_carries_records_permissions(client) -> None:
    response = await client.post(
        "/v1/auth/register", json={"identifier": "records-rbac@example.com", "password": "Records-pass-1234", "locale": "en"}
    )
    assert response.status_code == 201, response.text
    introspect = await client.post(
        "/v1/auth/introspect",
        json={"token": response.json()["access_token"]},
        headers={"X-Service-Client-Id": settings.service_auth_client_id, "X-Service-Client-Secret": settings.service_auth_client_secret},
    )
    assert RECORDS <= set(introspect.json()["perms"])
