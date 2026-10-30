"""Keeps appointments.payment_status in sync with payment-service.

payment-service owns money; this service only mirrors the outcome so the booking lifecycle can
gate confirmation on payment (see ``settings.payment_required`` and ``PAID_STATUSES`` in
domain/booking.py). Only events whose subject is an appointment are applied. Status moves forward
only (pending → authorized → captured → refunded), so redelivered or late events never regress it;
the one backwards move is a voided authorisation returning a booking to ``pending``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection, subject_for
from sqlalchemy import select

from appointment_service.infra.db import SessionLocal
from appointment_service.infra.models import Appointment

logger = logging.getLogger(__name__)

RANK = {"not_required": 0, "pending": 1, "authorized": 2, "captured": 3, "refunded": 4}


def _target(event_type: str, payload: dict[str, Any]) -> str | None:
    if event_type == "payment.authorized":
        return "authorized"
    if event_type == "payment.succeeded":
        return "captured"
    if event_type == "payment.refunded":
        return "refunded" if payload.get("fully_refunded") else None  # partial refunds keep "captured"
    if event_type == "payment.canceled":
        return "pending"
    return None


async def handle_payment_event(envelope: dict[str, Any]) -> None:
    payload = envelope.get("payload") or {}
    if payload.get("subject_type") != "appointment" or not payload.get("subject_id"):
        return  # memberships, concierge services, etc. are not ours
    target = _target(envelope.get("type", ""), payload)
    if target is None:
        return
    async with SessionLocal() as db:
        appointment = await db.scalar(
            select(Appointment)
            .where(Appointment.id == payload["subject_id"], Appointment.tenant_id == envelope.get("tenant_id"))
            .with_for_update()
        )
        if appointment is None:
            logger.warning("payment event %s for unknown appointment %s", envelope.get("event_id"), payload["subject_id"])
            return
        current = appointment.payment_status
        voided = target == "pending" and current == "authorized"
        if current == "not_required" or not (voided or RANK[target] > RANK[current]):
            return  # nothing to do, or an out-of-order/duplicate event
        appointment.payment_status = target
        appointment.updated_at = datetime.now(UTC)
        await db.commit()


def build_consumers(connection: JetStreamConnection) -> list[DurableConsumer]:
    return [
        DurableConsumer(
            connection,
            subject=subject_for(event_type),
            durable=f"appointment-service-{event_type.replace('.', '-')}",
            handler=handle_payment_event,
        )
        for event_type in ("payment.authorized", "payment.succeeded", "payment.refunded", "payment.canceled")
    ]
