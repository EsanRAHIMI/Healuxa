"""Journey RBAC on default user role — transformation.openapi.yaml permissions."""

from __future__ import annotations

from ulid import ULID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role

JOURNEY_PERMISSIONS = ("journeys:create", "journeys:read", "journeys:write")


@pytest.mark.asyncio
async def test_default_user_role_includes_journey_permissions() -> None:
    async with SessionLocal() as db:
        role = await db.scalar(
            select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == "user")
        )
    assert role is not None
    permissions = set(role.permissions or [])
    for permission in JOURNEY_PERMISSIONS:
        assert permission in permissions
    assert "sessions:revoke" in permissions


@pytest.mark.asyncio
async def test_register_introspect_includes_journey_permissions(
    client: AsyncClient,
    service_headers: dict,
) -> None:
    email = f"journey-rbac-{ULID()}@example.com"
    register = await client.post(
        "/v1/auth/register",
        json={"identifier": email, "password": "password123", "locale": "en"},
    )
    assert register.status_code == 201, register.text

    introspect = await client.post(
        "/v1/auth/introspect",
        json={"token": register.json()["access_token"]},
        headers=service_headers,
    )
    assert introspect.status_code == 200
    perms = set(introspect.json().get("perms") or [])
    for permission in JOURNEY_PERMISSIONS:
        assert permission in perms
