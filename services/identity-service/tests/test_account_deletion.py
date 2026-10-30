"""Self-service account deletion: re-auth, anonymisation, session revocation, event."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from ulid import ULID

from identity_service.infra.db import SessionLocal
from identity_service.infra.models import OUTBOX, User


async def test_delete_account_end_to_end(client: AsyncClient, service_headers: dict) -> None:
    email = f"delete-{ULID()}@example.com"
    tokens = (await client.post("/v1/auth/register", json={"identifier": email, "password": "password123", "locale": "en"})).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert (await client.post("/v1/auth/delete-account", json={"password": "wrong-pass"}, headers=auth)).status_code == 401
    assert (await client.post("/v1/auth/delete-account", json={"password": "password123"}, headers=auth)).status_code == 204

    introspect = await client.post("/v1/auth/introspect", json={"token": tokens["access_token"]}, headers=service_headers)
    assert introspect.json()["active"] is False
    assert (await client.post("/v1/auth/login", json={"identifier": email, "password": "password123"})).status_code == 401
    # The e-mail is free again.
    assert (await client.post("/v1/auth/register", json={"identifier": email, "password": "password123", "locale": "en"})).status_code == 201

    async with SessionLocal() as db:
        deleted = await db.scalar(select(User).where(User.status == "deleted"))
        events = (await db.execute(select(OUTBOX.c.body).where(OUTBOX.c.event_type == "auth.user_deleted"))).all()
    assert deleted is not None and deleted.identifier == f"deleted:{deleted.id}"
    assert [e.body["payload"]["user_id"] for e in events] == [deleted.id]
