"""Durable JetStream pull consumer with explicit acks, bounded redelivery and a dead-letter stream.

Handlers must be idempotent on ``event_id`` (delivery is at-least-once). A handler that raises is
retried with backoff; after ``max_deliver`` attempts the message is copied to the DLQ stream with the
failure reason and terminated, so one poison message never blocks the subject.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from healuxa_py_common.events.jetstream import (
    DLQ_STREAM,
    EVENTS_STREAM,
    JetStreamConnection,
    dlq_subject_for,
)
from healuxa_py_common.observability.metrics import EVENTS_CONSUMED
from healuxa_py_common.observability.tracing import bind_trace_id

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]

DEFAULT_BACKOFF = (1.0, 5.0, 30.0, 120.0)


class DurableConsumer:
    def __init__(
        self,
        connection: JetStreamConnection,
        *,
        subject: str,
        durable: str,
        handler: Handler,
        max_deliver: int = 5,
        ack_wait: float = 30.0,
        batch_size: int = 10,
        backoff: tuple[float, ...] = DEFAULT_BACKOFF,
    ) -> None:
        self._connection = connection
        self._subject = subject
        self._durable = durable
        self._handler = handler
        self._max_deliver = max_deliver
        self._ack_wait = ack_wait
        self._batch_size = batch_size
        self._backoff = backoff
        self._sub: Any = None

    async def _subscription(self) -> Any:
        if self._sub is None:
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

            js = await self._connection.jetstream()
            self._sub = await js.pull_subscribe(
                self._subject,
                durable=self._durable,
                stream=EVENTS_STREAM,
                config=ConsumerConfig(
                    durable_name=self._durable,
                    ack_policy=AckPolicy.EXPLICIT,
                    deliver_policy=DeliverPolicy.ALL,
                    ack_wait=self._ack_wait,
                    max_deliver=self._max_deliver,
                    filter_subject=self._subject,
                ),
            )
        return self._sub

    async def run_once(self, *, timeout: float = 1.0) -> int:
        """Fetch and process one batch. Returns the number of messages handled (acked or dead-lettered)."""
        from nats.errors import TimeoutError as NatsTimeoutError

        sub = await self._subscription()
        try:
            messages = await sub.fetch(self._batch_size, timeout=timeout)
        except NatsTimeoutError:
            return 0
        for msg in messages:
            await self._process(msg)
        return len(messages)

    async def _process(self, msg: Any) -> None:
        delivered = msg.metadata.num_delivered
        try:
            envelope = json.loads(msg.data)
        except ValueError as exc:
            await self._dead_letter(msg, reason=f"undecodable payload: {exc}")
            return
        with bind_trace_id(envelope.get("trace_id") or envelope.get("correlation_id")):
            try:
                await self._handler(envelope)
            except Exception as exc:  # noqa: BLE001 — retried, then dead-lettered with the reason
                if delivered >= self._max_deliver:
                    logger.error(
                        "event %s exhausted %d deliveries on %s: %s",
                        envelope.get("event_id"),
                        delivered,
                        self._durable,
                        exc,
                    )
                    await self._dead_letter(msg, reason=f"{type(exc).__name__}: {exc}")
                    return
                delay = self._backoff[min(delivered - 1, len(self._backoff) - 1)]
                logger.warning(
                    "event %s failed on %s (delivery %d), retrying in %.0fs: %s",
                    envelope.get("event_id"),
                    self._durable,
                    delivered,
                    delay,
                    exc,
                )
                await msg.nak(delay=delay)
                EVENTS_CONSUMED.labels(self._durable, "retried").inc()
                return
        await msg.ack()
        EVENTS_CONSUMED.labels(self._durable, "acked").inc()

    async def _dead_letter(self, msg: Any, *, reason: str) -> None:
        js = await self._connection.jetstream()
        await js.publish(
            dlq_subject_for(msg.subject),
            msg.data,
            stream=DLQ_STREAM,
            headers={
                "Healuxa-Dlq-Reason": reason[:500],
                "Healuxa-Dlq-Consumer": self._durable,
                "Healuxa-Dlq-Deliveries": str(msg.metadata.num_delivered),
                "Healuxa-Original-Subject": msg.subject,
            },
        )
        await msg.term()
        EVENTS_CONSUMED.labels(self._durable, "dead_lettered").inc()

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.run_once(timeout=1.0)
            except Exception:  # noqa: BLE001 — broker outage: back off and reconnect
                logger.exception("consumer %s iteration failed", self._durable)
                self._sub = None
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2.0)
                except TimeoutError:
                    pass
