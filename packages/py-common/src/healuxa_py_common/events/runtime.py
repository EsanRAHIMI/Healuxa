"""Background event tasks (outbox relay + durable consumers) bound to a FastAPI lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection
from healuxa_py_common.events.outbox import JetStreamPublisher, OutboxRelay, OutboxStore

logger = logging.getLogger(__name__)


class EventRuntime:
    def __init__(self, *, nats_url: str, service_name: str) -> None:
        self.connection = JetStreamConnection(nats_url, name=service_name)
        self._relays: list[OutboxRelay] = []
        self._consumers: list[DurableConsumer] = []
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def add_outbox(self, store: OutboxStore) -> OutboxRelay:
        relay = OutboxRelay(store, JetStreamPublisher(self.connection))
        self._relays.append(relay)
        return relay

    def add_consumer(self, consumer: DurableConsumer) -> None:
        self._consumers.append(consumer)

    async def start(self) -> None:
        self._stop.clear()
        for worker in [*self._relays, *self._consumers]:
            self._tasks.append(asyncio.create_task(worker.run_forever(self._stop)))
        logger.info("event runtime started: %d relay(s), %d consumer(s)", len(self._relays), len(self._consumers))

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=10)
        self._tasks.clear()
        await self.connection.close()
