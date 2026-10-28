from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from profile_service.config import settings

_client: AsyncMongoClient | None = None


def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not configured")
        _client = AsyncMongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        )
    return _client


def get_database() -> AsyncDatabase:
    return get_client()[settings.mongodb_database]


async def close_client() -> None:
    global _client
    # The client is bound to the event loop that created it; always release it
    # so a later loop (new test, app restart) never reuses a stale instance.
    client, _client = _client, None
    if client is not None:
        await client.close()


async def ensure_indexes() -> None:
    db = get_database()
    await db["customer_profiles"].create_index(
        [("tenant_id", 1), ("user_id", 1)],
        unique=True,
        name="uq_customer_profiles_tenant_user",
    )
    await db["customer_profiles"].create_index(
        [("tenant_id", 1), ("updated_at", -1)],
        name="ix_customer_profiles_tenant_updated",
    )


async def ping_database() -> None:
    await get_client().admin.command("ping")
