"""Identity events are staged in the same transaction as the change that caused them."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from identity_service.infra.db import SessionLocal
from identity_service.infra.models import OUTBOX


async def _events(event_type: str) -> list[dict]:
    async with SessionLocal() as db:
        rows = await db.execute(select(OUTBOX).where(OUTBOX.c.event_type == event_type))
        return [dict(row._mapping) for row in rows]


async def test_register_stages_user_registered(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"identifier": f"user-{ULID()}@example.com", "password": "password123", "locale": "en"},
    )
    assert response.status_code == 201, response.text

    [event] = await _events("auth.user_registered")
    assert event["status"] == "pending"
    assert event["subject"] == "healuxa.auth.user_registered.v1"
    assert event["body"]["event_id"] == event["event_id"]
    assert event["body"]["trace_id"] == response.headers["X-Trace-Id"]


async def test_duplicate_registration_stages_no_event(client: AsyncClient) -> None:
    body = {"identifier": f"user-{ULID()}@example.com", "password": "password123", "locale": "en"}
    assert (await client.post("/v1/auth/register", json=body)).status_code == 201
    assert (await client.post("/v1/auth/register", json=body)).status_code == 409
    assert len(await _events("auth.user_registered")) == 1


async def test_logout_stages_session_revoked(client: AsyncClient) -> None:
    register = await client.post(
        "/v1/auth/register",
        json={"identifier": f"user-{ULID()}@example.com", "password": "password123", "locale": "en"},
    )
    access_token = register.json()["access_token"]
    logout = await client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout.status_code == 204, logout.text

    [event] = await _events("auth.session_revoked")
    assert event["body"]["payload"]["reason"] == "logout"
