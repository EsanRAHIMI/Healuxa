from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from concierge_service.api.deps import principal_headers
from concierge_service.infra.db import SessionLocal
from concierge_service.infra.models import OUTBOX

CUSTOMER_PERMS = "concierge:request"
COORDINATOR_PERMS = "concierge:coordinate"
SUPERVISOR_PERMS = "concierge:coordinate,concierge:supervise"
OTHER_TENANT = "healuxa-europe"

CASE_BODY = {
    "category": "medical_travel",
    "preferred_start_date": "2026-12-01",
    "preferred_end_date": "2026-12-10",
    "languages": ["en", "ar"],
    "destination_city": "Dubai",
    "needs_note": "Wheelchair-accessible hotel near the clinic; arriving with one companion.",
}


def new_user() -> str:
    return str(ULID())


def customer(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=CUSTOMER_PERMS, tenant_id=tenant_id)


def coordinator(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=COORDINATOR_PERMS, tenant_id=tenant_id)


def supervisor(user_id: str, *, tenant_id: str | None = None) -> dict[str, str]:
    return principal_headers(user_id, permissions=SUPERVISOR_PERMS, tenant_id=tenant_id)


async def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def create_case(client: AsyncClient, owner: str, **overrides) -> dict:
    return await ok(await client.post("/v1/concierge/cases", json={**CASE_BODY, **overrides}, headers=customer(owner)), 201)


async def move(client: AsyncClient, case_id: str, headers: dict, to_status: str, reason: str | None = None, expect: int = 200) -> dict:
    body = {"to_status": to_status}
    if reason is not None:
        body["reason"] = reason
    return await ok(await client.post(f"/v1/concierge/cases/{case_id}/transitions", json=body, headers=headers), expect)


async def claim(client: AsyncClient, case_id: str, coordinator_id: str) -> dict:
    return await ok(await client.post(f"/v1/concierge/cases/{case_id}/assignment", json={}, headers=coordinator(coordinator_id)))


async def working_case(client: AsyncClient) -> dict:
    """A case claimed by a coordinator and in progress."""
    owner, coord = new_user(), new_user()
    case = await create_case(client, owner)
    await claim(client, case["id"], coord)
    case = await move(client, case["id"], coordinator(coord), "in_progress")
    return {"owner": owner, "coordinator": coord, "case": case}


async def propose(client: AsyncClient, case_id: str, coord: str, **overrides) -> dict:
    body = {"provider_id": str(ULID()), "branch_id": str(ULID()), "label": "Option A — Jumeirah branch", **overrides}
    return await ok(await client.post(f"/v1/concierge/cases/{case_id}/options", json=body, headers=coordinator(coord)), 201)


async def outbox_events(event_type: str | None = None) -> list[dict]:
    async with SessionLocal() as db:
        stmt = select(OUTBOX.c.body).order_by(OUTBOX.c.created_at)
        if event_type:
            stmt = stmt.where(OUTBOX.c.event_type == event_type)
        return [row.body for row in await db.execute(stmt)]
