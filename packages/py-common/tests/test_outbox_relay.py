from __future__ import annotations

from datetime import UTC, datetime, timedelta

from healuxa_py_common.events.envelope import build_envelope
from healuxa_py_common.events.outbox import (
    MAX_BACKOFF,
    OutboxMessage,
    OutboxRelay,
    outbox_fields,
    retry_delay,
)
from healuxa_py_common.observability.tracing import bind_trace_id


class FakeStore:
    def __init__(self, messages: list[OutboxMessage]) -> None:
        self.pending = {m.event_id: m for m in messages}
        self.published: list[str] = []
        self.failed: dict[str, tuple[str, datetime]] = {}

    async def claim_batch(self, *, limit: int, lease: timedelta) -> list[OutboxMessage]:
        return list(self.pending.values())[:limit]

    async def mark_published(self, event_id: str) -> None:
        self.pending.pop(event_id)
        self.published.append(event_id)

    async def mark_failed(self, event_id: str, *, error: str, retry_at: datetime) -> None:
        self.failed[event_id] = (error, retry_at)

    async def pending_count(self) -> int:
        return len(self.pending)


class FlakyPublisher:
    def __init__(self, fail_ids: set[str]) -> None:
        self.fail_ids = fail_ids
        self.sent: list[str] = []

    async def publish(self, message: OutboxMessage) -> None:
        if message.event_id in self.fail_ids:
            raise ConnectionError("broker unavailable")
        self.sent.append(message.event_id)


def _message(event_id: str, attempts: int = 0) -> OutboxMessage:
    return OutboxMessage(event_id=event_id, subject="healuxa.test.happened.v1", body={}, attempts=attempts)


async def test_relay_publishes_and_marks_in_order() -> None:
    store = FakeStore([_message("a"), _message("b")])
    publisher = FlakyPublisher(set())

    assert await OutboxRelay(store, publisher).run_once() == 2
    assert publisher.sent == ["a", "b"]
    assert store.published == ["a", "b"]


async def test_failed_publish_stays_pending_with_backoff() -> None:
    store = FakeStore([_message("a"), _message("b", attempts=3)])
    publisher = FlakyPublisher({"b"})
    before = datetime.now(UTC)

    assert await OutboxRelay(store, publisher).run_once() == 1

    assert store.published == ["a"]
    assert "b" in store.pending, "a failed publish must never be dropped"
    error, retry_at = store.failed["b"]
    assert "broker unavailable" in error
    assert retry_at >= before + timedelta(seconds=8)  # 4th attempt → 2**3 seconds


def test_retry_delay_is_exponential_and_capped() -> None:
    assert [retry_delay(n).total_seconds() for n in (1, 2, 3)] == [1, 2, 4]
    assert retry_delay(50) == MAX_BACKOFF


def test_envelope_inherits_active_trace_as_correlation() -> None:
    with bind_trace_id("trace-123"):
        envelope = build_envelope(
            event_type="assessment.completed",
            version=1,
            schema_ref="ref",
            tenant_id="t",
            producer="assessment-service",
            payload={},
            allowed_producers={"assessment-service"},
        )
    assert envelope.trace_id == "trace-123"
    assert envelope.correlation_id == "trace-123"
    fields = outbox_fields(envelope)
    assert fields["subject"] == "healuxa.assessment.completed.v1"
    assert fields["body"]["event_id"] == envelope.event_id
