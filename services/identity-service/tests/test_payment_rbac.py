"""payment/subscription RBAC (migration 0010): customers pay and read their own; finance staff manage money."""

from __future__ import annotations

from sqlalchemy import select

from identity_service.config import settings
from identity_service.infra.db import SessionLocal
from identity_service.infra.models import Role

STAFF_ONLY = {"payments:manage", "payments:refund", "finance:reconcile", "subscriptions:manage"}


async def _permissions(role_name: str) -> set[str]:
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.tenant_id == settings.tenant_default, Role.name == role_name))
    assert role is not None
    return set(role.permissions or [])


async def test_user_role_can_pay_but_not_manage_money() -> None:
    perms = await _permissions("user")
    assert {"payments:create", "payments:read", "invoices:read", "subscriptions:create", "subscriptions:read"} <= perms
    assert not STAFF_ONLY & perms


async def test_admin_and_finance_roles_manage_money() -> None:
    assert STAFF_ONLY <= await _permissions("admin")
    finance = await _permissions("finance")
    assert {"payments:manage", "payments:refund", "finance:reconcile"} <= finance
    assert "subscriptions:manage" not in finance and "iam:write" not in finance
