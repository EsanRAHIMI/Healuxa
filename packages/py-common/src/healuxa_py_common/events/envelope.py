from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventActor(BaseModel):
    type: str
    id: str


class EventEnvelope(BaseModel):
    """Envelope per packages/event-contracts/schemas/envelope.schema.json."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    version: int
    schema_ref: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str
    producer: str
    payload: dict[str, Any]
    trace_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    actor: EventActor | None = None


def build_envelope(
    *,
    event_type: str,
    version: int,
    schema_ref: str,
    tenant_id: str,
    producer: str,
    payload: dict[str, Any],
    allowed_producers: set[str],
    trace_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    actor: EventActor | None = None,
) -> EventEnvelope:
    if producer not in allowed_producers:
        raise ValueError(f"Producer {producer!r} is not registered owner for {event_type!r}")
    return EventEnvelope(
        type=event_type,
        version=version,
        schema_ref=schema_ref,
        tenant_id=tenant_id,
        producer=producer,
        payload=payload,
        trace_id=trace_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        actor=actor,
    )
