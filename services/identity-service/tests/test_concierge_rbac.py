"""concierge-service / notification-service RBAC: customers request; only admins coordinate and supervise."""

from __future__ import annotations

from sqlalchemy import select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role


async def _permissions(role_name: str) -> set[str]:
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == role_name))
    assert role is not None
    return set(role.permissions or [])


async def test_user_role_can_request_concierge_and_manage_own_notifications() -> None:
    perms = await _permissions("user")
    assert {"concierge:request", "notifications:read", "notifications:write"} <= perms
    assert not {"concierge:coordinate", "concierge:supervise", "service"} & perms


async def test_admin_role_can_coordinate_and_supervise() -> None:
    assert {"concierge:coordinate", "concierge:supervise", "concierge:request"} <= await _permissions("admin")
