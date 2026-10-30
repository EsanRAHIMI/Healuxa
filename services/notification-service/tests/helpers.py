from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from notification_service.api.deps import principal_headers
from notification_service.infra.db import SessionLocal
from notification_service.infra.models import Delivery, Notification

USER_PERMS = "notifications:read,notifications:write"
TENANT = "healuxa-dubai"
OTHER_TENANT = "healuxa-europe"


def new_id() -> str:
    return str(ULID())


def user(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=USER_PERMS, tenant_id=tenant_id)


def service(*, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers("healuxa-internal", permissions="service", tenant_id=tenant_id)


async def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def send(client: AsyncClient, user_id: str, template: str = "account.notice", *, key: str | None = None, expect: int = 202, **extra) -> dict:
    headers = service()
    if key:
        headers["Idempotency-Key"] = key
    return await ok(await client.post("/v1/notifications/send", json={"user_id": user_id, "template": template, **extra}, headers=headers), expect)


async def set_prefs(client: AsyncClient, user_id: str, body: dict) -> dict:
    return await ok(await client.put(f"/v1/notifications/preferences/{user_id}", json=body, headers=user(user_id)))


def envelope(event_type: str, payload: dict[str, Any], *, tenant_id: str = TENANT, event_id: str | None = None) -> dict:
    return {
        "event_id": event_id or new_id(),
        "type": event_type,
        "version": 1,
        "schema_ref": f"https://contracts.healuxa.com/events/x.schema.json#/$defs/{event_type}",
        "occurred_at": datetime.now(UTC).isoformat(),
        "tenant_id": tenant_id,
        "producer": "test",
        "payload": payload,
    }


def status_changed(customer_id: str, status: str = "in_progress", *, coordinator_id: str | None = None, case_id: str | None = None) -> dict:
    return envelope(
        "concierge.case_status_changed",
        {
            "case_id": case_id or new_id(),
            "customer_id": customer_id,
            "coordinator_id": coordinator_id,
            "previous_status": "assigned",
            "status": status,
            "changed_by_role": "coordinator",
            "changed_at": datetime.now(UTC).isoformat(),
        },
    )


async def deliveries(user_id: str) -> dict[str, Delivery]:
    async with SessionLocal() as db:
        rows = await db.scalars(select(Delivery).where(Delivery.user_id == user_id))
        return {d.channel: d for d in rows}


async def notifications_of(user_id: str) -> list[Notification]:
    async with SessionLocal() as db:
        return list(await db.scalars(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at)))
