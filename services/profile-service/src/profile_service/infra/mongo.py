from __future__ import annotations

from healuxa_py_common.events.outbox_mongo import OUTBOX_COLLECTION, ensure_outbox_indexes
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
    await ensure_outbox_indexes(db[OUTBOX_COLLECTION])
    await db["customer_profiles"].create_index(
        [("tenant_id", 1), ("user_id", 1)],
        unique=True,
        name="uq_customer_profiles_tenant_user",
    )
    await db["customer_profiles"].create_index(
        [("tenant_id", 1), ("updated_at", -1)],
        name="ix_customer_profiles_tenant_updated",
    )
    # Medical records, consent grants and the access log.
    await db["medical_records"].create_index(
        [("tenant_id", 1), ("user_id", 1), ("created_at", -1)], name="ix_medical_records_owner"
    )
    await db["record_grants"].create_index(
        [("tenant_id", 1), ("user_id", 1), ("created_at", -1)], name="ix_record_grants_owner"
    )
    await db["record_grants"].create_index(
        [("tenant_id", 1), ("grantee_type", 1), ("grantee_id", 1), ("expires_at", -1)], name="ix_record_grants_grantee"
    )
    await db["record_grants"].create_index([("record_ids", 1)], name="ix_record_grants_records")
    await db["record_access_log"].create_index(
        [("tenant_id", 1), ("owner_user_id", 1), ("record_id", 1), ("_id", -1)], name="ix_record_access_log_owner"
    )
    await db["record_access_log"].create_index(
        [("tenant_id", 1), ("actor_user_id", 1)], name="ix_record_access_log_actor"
    )
    await db["record_idempotency"].create_index(
        [("created_at", 1)], name="ttl_record_idempotency", expireAfterSeconds=7 * 24 * 3600
    )


async def ping_database() -> None:
    await get_client().admin.command("ping")
