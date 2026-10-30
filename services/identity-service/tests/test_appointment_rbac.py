"""appointment-service RBAC: users book and act on their own; only admins manage tenant-wide."""

from __future__ import annotations

from sqlalchemy import select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role

BOOKING = {"appointments:create", "appointments:read", "appointments:write"}


async def _permissions(role_name: str) -> set[str]:
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == role_name))
    assert role is not None
    return set(role.permissions or [])


async def test_user_role_can_book_but_not_manage() -> None:
    perms = await _permissions("user")
    assert BOOKING <= perms
    assert "appointments:manage" not in perms
    # Earlier grants are preserved.
    assert {"providers:onboard", "facilities:onboard"} <= perms


async def test_admin_role_can_manage_appointments() -> None:
    assert BOOKING | {"appointments:manage"} <= await _permissions("admin")
