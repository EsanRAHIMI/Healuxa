"""Durable-consumer handlers: appointment.* (booking engine) and subscription.* (memberships).

Handlers are idempotent on ``event_id`` (consumed_events) and every side effect is itself idempotent
(processor calls use deterministic idempotency keys; captures/voids of settled payments are no-ops),
so the marker is written last: a crash mid-handler simply re-runs it on redelivery.

Booking integration (confirm-then-charge): appointment.requested/created upserts the read model the
quote endpoint checks; appointment.accepted (or completed) captures the held authorisation;
appointment.declined voids it, or fully refunds if it was already captured.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_service.config import settings
from payment_service.domain import payments as payment_flow
from payment_service.domain import refunds as refund_flow
from payment_service.domain.quotes import membership_lines
from payment_service.domain.state import CAPTURED_FAMILY
from payment_service.infra.gateways import get_gateway
from payment_service.infra.gateways.stripe import interval_for
from payment_service.infra.models import AppointmentView, ConsumedEvent, MembershipView, Payment

logger = logging.getLogger(__name__)

APPOINTMENT_STATUS = {
    "appointment.requested": "requested",
    "appointment.created": "created",
    "appointment.accepted": "accepted",
    "appointment.declined": "declined",
    "appointment.completed": "completed",
    "appointment.no_show": "no_show",
}
SUBSCRIPTION_EVENTS = {"subscription.created", "subscription.upgraded", "subscription.downgraded", "subscription.cancellation_scheduled"}


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _already(db: AsyncSession, event_id: str) -> bool:
    return await db.get(ConsumedEvent, event_id) is not None


async def _mark(sessions: async_sessionmaker[AsyncSession], envelope: dict[str, Any]) -> None:
    async with sessions() as db, db.begin():
        await db.execute(
            insert(ConsumedEvent).values(event_id=envelope["event_id"], event_type=envelope["type"]).on_conflict_do_nothing()
        )


async def handle_appointment_event(sessions: async_sessionmaker[AsyncSession], envelope: dict[str, Any]) -> None:
    event_type = envelope["type"]
    if event_type not in APPOINTMENT_STATUS:
        return
    payload = envelope["payload"]
    tenant_id = envelope["tenant_id"]
    appointment_id = payload["appointment_id"]
    async with sessions() as db, db.begin():
        if await _already(db, envelope["event_id"]):
            return
        view = await db.scalar(select(AppointmentView).where(AppointmentView.appointment_id == appointment_id).with_for_update())
        status = APPOINTMENT_STATUS[event_type]
        if view is None:
            db.add(
                AppointmentView(
                    appointment_id=appointment_id,
                    tenant_id=tenant_id,
                    user_id=payload["user_id"],
                    provider_id=payload["provider_id"],
                    service_id=payload["service_id"],
                    scheduled_at=_dt(payload["scheduled_at"]),
                    status=status,
                )
            )
        elif view.status not in {"declined", "completed", "no_show"} or status in {"completed", "no_show"}:
            # Terminal outcomes are never overwritten by a late requested/created/accepted event.
            if not (view.status in {"accepted", "completed"} and status in {"requested", "created"}):
                view.status = status
            view.scheduled_at = _dt(payload["scheduled_at"])
        payment_ids = list(
            await db.scalars(
                select(Payment.id).where(
                    Payment.tenant_id == tenant_id, Payment.subject_type == "appointment", Payment.subject_id == appointment_id
                )
            )
        )
    for payment_id in payment_ids:
        async with sessions() as db:
            payment = await db.get(Payment, payment_id)
        if event_type in {"appointment.accepted", "appointment.completed"} and payment.status == "authorized":
            await payment_flow.capture(sessions, payment_id)
        elif event_type == "appointment.declined":
            if payment.status in {"pending", "processing", "failed", "authorized"} and payment.processor_payment_id:
                await payment_flow.cancel(sessions, payment_id, reason="provider_declined")
            elif payment.status in CAPTURED_FAMILY and refund_flow.remaining(payment) > 0:
                await refund_flow.create_refund(
                    sessions,
                    None,
                    tenant_id=tenant_id,
                    payment_id=payment_id,
                    body={"reason": "provider_declined"},
                    key=f"declined:{envelope['event_id']}",
                )
    await _mark(sessions, envelope)


async def handle_subscription_event(sessions: async_sessionmaker[AsyncSession], envelope: dict[str, Any]) -> None:
    event_type = envelope["type"]
    if event_type not in SUBSCRIPTION_EVENTS:
        return
    payload = envelope["payload"]
    subscription_id = payload["subscription_id"]
    async with sessions() as db, db.begin():
        if await _already(db, envelope["event_id"]):
            return
        view = await db.scalar(select(MembershipView).where(MembershipView.subscription_id == subscription_id).with_for_update())
        if event_type == "subscription.created":
            if view is None:
                db.add(
                    MembershipView(
                        subscription_id=subscription_id,
                        tenant_id=envelope["tenant_id"],
                        user_id=payload["user_id"],
                        plan_id=payload["plan_id"],
                        price_minor=int(payload["price"]["amount_minor"]),
                        currency=payload["price"]["currency"],
                        billing_cycle=payload["billing_cycle"],
                    )
                )
            await db.flush()
            action = None
        elif view is None:
            logger.warning("%s for unknown subscription %s", event_type, subscription_id)
            action = None
        elif event_type in {"subscription.upgraded", "subscription.downgraded"}:
            view.plan_id = payload["to_plan_id"]
            if payload.get("price"):
                view.price_minor = int(payload["price"]["amount_minor"])
            if payload.get("billing_cycle"):
                view.billing_cycle = payload["billing_cycle"]
            view.lines = [line.as_dict() for line in membership_lines(view.price_minor, view.plan_id, view.billing_cycle)]
            action = "reprice" if view.processor_subscription_id and view.processor_item_id else None
        else:  # cancellation_scheduled
            view.cancel_at_period_end = True
            action = "cancel" if view.processor_subscription_id else None
        snapshot = (view.processor_subscription_id, view.processor_item_id, view.lines, view.plan_id, view.billing_cycle, view.currency) if view else None
    if action and settings.membership_payments_enabled:
        sub_id, item_id, lines, plan_id, cycle, currency = snapshot
        gateway = get_gateway()
        key = f"hx-subupd-{envelope['event_id']}"
        if action == "cancel":
            await gateway.update_subscription(sub_id, idempotency_key=key, cancel_at_period_end=True)
        else:
            interval, count = interval_for(cycle)
            gross = sum(int(line["gross_minor"]) for line in lines or [])
            await gateway.update_subscription(
                sub_id,
                idempotency_key=key,
                item_id=item_id,
                amount_minor=gross,
                currency=currency,
                interval=interval,
                interval_count=count,
                product_name=f"Healuxa membership {plan_id}",
            )
    await _mark(sessions, envelope)


async def dispatch(sessions: async_sessionmaker[AsyncSession], envelope: dict[str, Any]) -> None:
    if envelope.get("type", "").startswith("appointment."):
        await handle_appointment_event(sessions, envelope)
    elif envelope.get("type", "").startswith("subscription."):
        await handle_subscription_event(sessions, envelope)
