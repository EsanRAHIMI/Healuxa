"""Transactional outbox: events are written with the business change, then relayed to JetStream.

Guarantees: an event is published at least once after its transaction commits, and never if the
transaction rolls back. Duplicates from relay crashes are absorbed by JetStream's Nats-Msg-Id window
and by idempotent consumers keyed on ``event_id``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from healuxa_py_common.events.envelope import EventEnvelope
from healuxa_py_common.events.jetstream import EVENTS_STREAM, JetStreamConnection, subject_for
from healuxa_py_common.observability.metrics import OUTBOX_PUBLISH_FAILURES, OUTBOX_PUBLISHED

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PUBLISHED = "published"

LEASE_DURATION = timedelta(seconds=30)
MAX_BACKOFF = timedelta(minutes=5)


@dataclass(frozen=True)
class OutboxMessage:
    event_id: str
    subject: str
    body: dict[str, Any]
    attempts: int


def outbox_fields(envelope: EventEnvelope) -> dict[str, Any]:
    """Column/field values for a new outbox entry; stores persist these verbatim."""
    now = datetime.now(UTC)
    return {
        "event_id": envelope.event_id,
        "event_type": envelope.type,
        "subject": subject_for(envelope.type, envelope.version),
        "tenant_id": envelope.tenant_id,
        "body": envelope.model_dump(mode="json"),
        "status": STATUS_PENDING,
        "attempts": 0,
        "available_at": now,
        "created_at": now,
        "published_at": None,
        "last_error": None,
    }


def retry_delay(attempts: int) -> timedelta:
    """Exponential backoff: 1s, 2s, 4s ... capped at MAX_BACKOFF."""
    exponent = min(max(attempts - 1, 0), 30)  # bound the exponent: long outages must not overflow
    return min(timedelta(seconds=2**exponent), MAX_BACKOFF)


class OutboxStore(Protocol):
    async def claim_batch(self, *, limit: int, lease: timedelta) -> list[OutboxMessage]:
        """Lease up to ``limit`` due messages so concurrent relays never publish the same row at once."""

    async def mark_published(self, event_id: str) -> None: ...

    async def mark_failed(self, event_id: str, *, error: str, retry_at: datetime) -> None: ...

    async def pending_count(self) -> int: ...


class Publisher(Protocol):
    async def publish(self, message: OutboxMessage) -> None: ...


class JetStreamPublisher:
    def __init__(self, connection: JetStreamConnection, *, timeout: float = 5.0) -> None:
        self._connection = connection
        self._timeout = timeout

    async def publish(self, message: OutboxMessage) -> None:
        js = await self._connection.jetstream()
        ack = await js.publish(
            message.subject,
            json.dumps(message.body, separators=(",", ":")).encode(),
            timeout=self._timeout,
            stream=EVENTS_STREAM,
            headers={"Nats-Msg-Id": message.event_id},
        )
        if ack.stream != EVENTS_STREAM:
            raise RuntimeError(f"event {message.event_id} acked by unexpected stream {ack.stream!r}")


class OutboxRelay:
    def __init__(
        self,
        store: OutboxStore,
        publisher: Publisher,
        *,
        batch_size: int = 100,
        idle_interval: float = 1.0,
    ) -> None:
        self._store = store
        self._publisher = publisher
        self._batch_size = batch_size
        self._idle_interval = idle_interval

    async def run_once(self) -> int:
        """Publish one batch. Returns the number of messages successfully published."""
        published = 0
        for message in await self._store.claim_batch(limit=self._batch_size, lease=LEASE_DURATION):
            try:
                await self._publisher.publish(message)
            except Exception as exc:  # noqa: BLE001 — every failure is recorded and retried
                attempts = message.attempts + 1
                OUTBOX_PUBLISH_FAILURES.labels(message.subject).inc()
                logger.warning(
                    "outbox publish failed event_id=%s subject=%s attempt=%d: %s",
                    message.event_id,
                    message.subject,
                    attempts,
                    exc,
                )
                await self._store.mark_failed(
                    message.event_id,
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                    retry_at=datetime.now(UTC) + retry_delay(attempts),
                )
                continue
            await self._store.mark_published(message.event_id)
            OUTBOX_PUBLISHED.labels(message.subject).inc()
            published += 1
        return published

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                published = await self.run_once()
            except Exception:  # noqa: BLE001 — store outage must not kill the relay task
                logger.exception("outbox relay iteration failed")
                published = 0
            if published < self._batch_size:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self._idle_interval)
                except TimeoutError:
                    pass
