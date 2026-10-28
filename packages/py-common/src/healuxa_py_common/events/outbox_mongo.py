"""MongoDB outbox store (PyMongo async). Enqueue inside the same session/transaction as the business write."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.collection import AsyncCollection

from healuxa_py_common.events.envelope import EventEnvelope
from healuxa_py_common.events.outbox import STATUS_PENDING, STATUS_PUBLISHED, OutboxMessage, outbox_fields

OUTBOX_COLLECTION = "outbox_events"


async def ensure_outbox_indexes(collection: AsyncCollection) -> None:
    await collection.create_index(
        [("status", ASCENDING), ("available_at", ASCENDING), ("created_at", ASCENDING)],
        name="ix_outbox_events_pending",
    )


async def enqueue(
    collection: AsyncCollection,
    envelope: EventEnvelope,
    *,
    session: AsyncClientSession | None = None,
) -> None:
    fields = outbox_fields(envelope)
    document: dict[str, Any] = {"_id": fields.pop("event_id"), **fields}
    await collection.insert_one(document, session=session)


class MongoOutboxStore:
    def __init__(self, collection: AsyncCollection) -> None:
        self._collection = collection

    async def claim_batch(self, *, limit: int, lease: timedelta) -> list[OutboxMessage]:
        claimed: list[OutboxMessage] = []
        now = datetime.now(UTC)
        for _ in range(limit):
            doc = await self._collection.find_one_and_update(
                {"status": STATUS_PENDING, "available_at": {"$lte": now}},
                {"$set": {"available_at": now + lease}},
                sort=[("created_at", ASCENDING)],
                return_document=ReturnDocument.AFTER,
            )
            if doc is None:
                break
            claimed.append(
                OutboxMessage(
                    event_id=doc["_id"],
                    subject=doc["subject"],
                    body=doc["body"],
                    attempts=int(doc.get("attempts", 0)),
                )
            )
        return claimed

    async def mark_published(self, event_id: str) -> None:
        await self._collection.update_one(
            {"_id": event_id},
            {"$set": {"status": STATUS_PUBLISHED, "published_at": datetime.now(UTC), "last_error": None}},
        )

    async def mark_failed(self, event_id: str, *, error: str, retry_at: datetime) -> None:
        await self._collection.update_one(
            {"_id": event_id},
            {"$set": {"last_error": error, "available_at": retry_at}, "$inc": {"attempts": 1}},
        )

    async def pending_count(self) -> int:
        return await self._collection.count_documents({"status": STATUS_PENDING})
