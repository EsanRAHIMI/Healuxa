"""JetStream connectivity shared by outbox relays and durable consumers.

Subjects follow ``healuxa.<event_type>.v<version>`` (TechSpec event naming). All domain events live in
one file-backed stream; exhausted deliveries are copied to a separate dead-letter stream for replay.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nats.aio.client import Client
    from nats.js.client import JetStreamContext

logger = logging.getLogger(__name__)

EVENTS_STREAM = "HEALUXA_EVENTS"
# Event types are always "<context>.<name>", so subjects have exactly four tokens.
EVENTS_SUBJECTS = ["healuxa.*.*.*"]
DLQ_STREAM = "HEALUXA_DLQ"
# Separate root so DLQ subjects can never overlap EVENTS_SUBJECTS (JetStream rejects overlaps).
DLQ_PREFIX = "healuxa_dlq"

# Publishers set Nats-Msg-Id to the envelope event_id; JetStream drops repeats inside this window,
# so an outbox relay that crashes between publish and mark-published does not duplicate events.
DUPLICATE_WINDOW = timedelta(minutes=10)


def subject_for(event_type: str, version: int = 1) -> str:
    return f"healuxa.{event_type}.v{version}"


def dlq_subject_for(subject: str) -> str:
    return f"{DLQ_PREFIX}.{subject.removeprefix('healuxa.')}"


async def ensure_streams(js: JetStreamContext) -> None:
    """Create or update the events and DLQ streams. Idempotent; safe on every service start."""
    from nats.js.api import RetentionPolicy, StorageType, StreamConfig
    from nats.js.errors import NotFoundError

    configs = [
        StreamConfig(
            name=EVENTS_STREAM,
            subjects=EVENTS_SUBJECTS,
            storage=StorageType.FILE,
            retention=RetentionPolicy.LIMITS,
            max_age=timedelta(days=14).total_seconds(),
            duplicate_window=DUPLICATE_WINDOW.total_seconds(),
        ),
        StreamConfig(
            name=DLQ_STREAM,
            subjects=[f"{DLQ_PREFIX}.>"],
            storage=StorageType.FILE,
            retention=RetentionPolicy.LIMITS,
            max_age=timedelta(days=30).total_seconds(),
        ),
    ]
    for config in configs:
        try:
            await js.stream_info(config.name)
            await js.update_stream(config)
        except NotFoundError:
            await js.add_stream(config)


class JetStreamConnection:
    """One lazily-opened NATS connection per process, shared by relay and consumers."""

    def __init__(self, url: str, *, name: str) -> None:
        self._url = url
        self._name = name
        self._nc: Client | None = None
        self._js: JetStreamContext | None = None
        self._lock = asyncio.Lock()

    async def jetstream(self) -> JetStreamContext:
        async with self._lock:
            if self._js is None or self._nc is None or self._nc.is_closed:
                import nats

                self._nc = await nats.connect(
                    self._url,
                    name=self._name,
                    connect_timeout=2,
                    max_reconnect_attempts=-1,
                )
                self._js = self._nc.jetstream()
                await ensure_streams(self._js)
            return self._js

    async def close(self) -> None:
        async with self._lock:
            if self._nc is not None and not self._nc.is_closed:
                # JetStream publishes are already acked; drain() would block on idle pull subscriptions.
                await self._nc.flush(timeout=2)
                await self._nc.close()
            self._nc = None
            self._js = None
