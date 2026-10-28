"""provider-service RBAC: customers may onboard; only admins may verify."""

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


async def test_user_role_can_onboard_but_not_verify() -> None:
    perms = await _permissions("user")
    assert {"providers:onboard", "facilities:onboard"} <= perms
    assert not {"providers:verify", "facilities:verify"} & perms


async def test_admin_role_can_verify() -> None:
    assert {"providers:verify", "facilities:verify"} <= await _permissions("admin")
