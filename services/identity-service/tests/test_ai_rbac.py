"""ai-orchestrator RBAC: customers and admins may use the assistant; providers' extra roles do not get it implicitly."""

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


async def test_user_role_can_chat_with_the_assistant() -> None:
    assert "ai:chat" in await _permissions("user")


async def test_admin_role_can_chat_with_the_assistant() -> None:
    assert "ai:chat" in await _permissions("admin")


async def test_finance_role_is_not_granted_chat() -> None:
    assert "ai:chat" not in await _permissions("finance")
