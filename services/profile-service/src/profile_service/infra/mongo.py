from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from profile_service.config import settings

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
