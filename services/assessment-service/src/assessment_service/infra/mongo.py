from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from assessment_service.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not configured")
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_database]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def ensure_indexes() -> None:
    db = get_database()
    await db["assessments"].create_index(
        [("tenant_id", 1), ("_id", 1)],
        unique=True,
        name="uq_assessments_tenant_id",
    )
    await db["assessments"].create_index(
        [("tenant_id", 1), ("user_id", 1), ("created_at", -1)],
        name="ix_assessments_tenant_user_created",
    )
    await db["idempotency_records"].create_index(
        [("key", 1)],
        unique=True,
        name="uq_idempotency_records_key",
    )


async def ping_database() -> None:
    await get_client().admin.command("ping")
