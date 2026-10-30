"""Event → notifications. Recipients are resolved from ids only: user ids carried by the event, or
recipient links registered for an entity (catalog events carry no owner id).

Idempotent on ``event_id`` (``processed_events``) and per (event, recipient, channel). A malformed
event raises, so the DurableConsumer retries it and finally dead-letters it.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from healuxa_py_common.events.consumer import DurableConsumer
from healuxa_py_common.events.jetstream import JetStreamConnection, subject_for
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.domain.notify import Recipient, notify
from notification_service.infra.db import SessionLocal
from notification_service.infra.models import ProcessedEvent, RecipientLink

logger = logging.getLogger(__name__)

CONSUMER_NAME = "notification-service"


class PoisonEvent(ValueError):
    """The event can never be processed (missing or invalid fields)."""


@dataclass(frozen=True)
class Planned:
    user_id: str
    template: str
    params: dict[str, object] = field(default_factory=dict)
    entity_type: str | None = None
    entity_id: str | None = None


def _require(payload: dict[str, Any], *keys: str) -> list[Any]:
    missing = [k for k in keys if not payload.get(k)]
    if missing:
        raise PoisonEvent(f"payload missing {missing}")
    return [payload[k] for k in keys]


async def _linked_users(db: AsyncSession, tenant_id: str, entity_type: str, entity_id: str) -> list[str]:
    rows = await db.scalars(
        select(RecipientLink.user_id).where(
            RecipientLink.tenant_id == tenant_id,
            RecipientLink.entity_type == entity_type,
            RecipientLink.entity_id == entity_id,
        )
    )
    return list(rows)


async def _concierge_status(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
    case_id, customer_id, status = _require(p, "case_id", "customer_id", "status")
    plans = [Planned(customer_id, "concierge.case_status_changed", {"status": status}, "concierge_case", case_id)]
    coordinator = p.get("coordinator_id")
    if status == "assigned" and coordinator and coordinator != customer_id:
        plans.append(Planned(coordinator, "concierge.case_assigned", {}, "concierge_case", case_id))
    return plans


async def _concierge_message(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
    case_id, customer_id, sender_id, sender_role = _require(p, "case_id", "customer_id", "sender_id", "sender_role")
    if sender_role == "coordinator":
        recipient = customer_id
    elif sender_role == "customer":
        recipient = p.get("coordinator_id")
    else:
        raise PoisonEvent(f"unknown sender_role {sender_role!r}")
    if not recipient or recipient == sender_id:
        return []
    return [Planned(recipient, "concierge.message_posted", {}, "concierge_case", case_id)]


async def _link(db: AsyncSession, tenant: str, entity_type: str, entity_id: str, user_id: str, role: str | None) -> None:
    """Idempotent upsert of a recipient link (events may be redelivered)."""
    await db.execute(
        pg_insert(RecipientLink)
        .values(tenant_id=tenant, entity_type=entity_type, entity_id=entity_id, user_id=user_id, role=role)
        .on_conflict_do_update(index_elements=["tenant_id", "entity_type", "entity_id", "user_id"], set_={"role": role})
    )


async def _provider_status(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
    provider_id, status = _require(p, "provider_id", "status")
    if p.get("owner_user_id"):
        # provider-service names the owner on every status event; keep the link current from it.
        await _link(db, tenant, "provider", provider_id, p["owner_user_id"], "owner")
    users = await _linked_users(db, tenant, "provider", provider_id)
    return [Planned(u, "catalog.provider_status_changed", {"status": status}, "provider", provider_id) for u in users]


async def _affiliation(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
    affiliation_id, provider_id, facility_id, status = _require(p, "affiliation_id", "provider_id", "facility_id", "status")
    users = await _linked_users(db, tenant, "provider", provider_id) + await _linked_users(db, tenant, "facility", facility_id)
    return [
        Planned(u, "catalog.affiliation_changed", {"status": status}, "provider", provider_id)
        for u in dict.fromkeys(users)
    ]


async def _facility_staff(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
    """Maintains facility recipients; produces no notification of its own."""
    facility_id, user_id, change = _require(p, "facility_id", "user_id", "change")
    if change == "added":
        await _link(db, tenant, "facility", facility_id, user_id, p.get("role"))
    else:
        await db.execute(
            delete(RecipientLink).where(
                RecipientLink.tenant_id == tenant,
                RecipientLink.entity_type == "facility",
                RecipientLink.entity_id == facility_id,
                RecipientLink.user_id == user_id,
            )
        )
    return []


def _appointment(template: str) -> Callable[[AsyncSession, str, dict[str, Any]], Awaitable[list[Planned]]]:
    async def plan(db: AsyncSession, tenant: str, p: dict[str, Any]) -> list[Planned]:
        appointment_id, user_id, scheduled_at = _require(p, "appointment_id", "user_id", "scheduled_at")
        return [Planned(user_id, template, {"scheduled_at": scheduled_at}, "appointment", appointment_id)]

    return plan


# Lifecycle events that exist (with notification-service as a consumer) in the registry of the
# appointment-service branch but not yet on main. Subscribing early is harmless: nothing is published
# on these subjects until appointment-service ships, and the merge order stays free.
AWAITING_REGISTRY_MERGE = frozenset(
    {"appointment.cancelled", "appointment.rescheduled", "appointment.expired", "appointment.reminder_due"}
)

# Events that only maintain recipient links.
MEMBERSHIP_EVENTS = frozenset({"catalog.facility_staff_changed"})

# Only events present in packages/event-contracts/src/registry.ts with notification-service listed.
PLANNERS: dict[str, Callable[[AsyncSession, str, dict[str, Any]], Awaitable[list[Planned]]]] = {
    "concierge.case_status_changed": _concierge_status,
    "concierge.message_posted": _concierge_message,
    "catalog.provider_status_changed": _provider_status,
    "catalog.affiliation_changed": _affiliation,
    "catalog.facility_staff_changed": _facility_staff,
    "appointment.requested": _appointment("appointment.requested"),
    "appointment.created": _appointment("appointment.created"),
    "appointment.accepted": _appointment("appointment.accepted"),
    "appointment.declined": _appointment("appointment.declined"),
    "appointment.completed": _appointment("appointment.completed"),
    "appointment.no_show": _appointment("appointment.no_show"),
    "appointment.cancelled": _appointment("appointment.cancelled"),
    "appointment.rescheduled": _appointment("appointment.rescheduled"),
    "appointment.expired": _appointment("appointment.expired"),
    "appointment.reminder_due": _appointment("appointment.reminder_due"),
}


async def process_event(envelope: dict[str, Any], *, db: AsyncSession) -> str:
    """Returns the outcome: ``notified``, ``no_recipient``, ``duplicate`` or ``ignored``."""
    event_id = envelope.get("event_id")
    event_type = envelope.get("type")
    tenant_id = envelope.get("tenant_id")
    payload = envelope.get("payload")
    if not event_id or not event_type or not tenant_id or not isinstance(payload, dict):
        raise PoisonEvent("not a Healuxa event envelope")
    if await db.get(ProcessedEvent, event_id) is not None:
        return "duplicate"
    planner = PLANNERS.get(event_type)
    plans = await planner(db, tenant_id, payload) if planner else []
    seen: set[str] = set()
    created = 0
    for plan in plans:
        if plan.user_id in seen:
            continue
        seen.add(plan.user_id)
        try:
            result = await notify(
                db,
                Recipient(tenant_id=tenant_id, user_id=plan.user_id),
                template_key=plan.template,
                params=plan.params,
                source_key=event_id,
                source_event_type=event_type,
                entity_type=plan.entity_type,
                entity_id=plan.entity_id,
            )
        except ValueError as exc:  # TemplateError: e.g. an enum value this catalog cannot render
            raise PoisonEvent(str(exc)) from exc
        created += int(result.created)
    if planner is None:
        outcome = "ignored"
    elif event_type in MEMBERSHIP_EVENTS:
        outcome = "applied"
    else:
        outcome = "notified" if plans else "no_recipient"
    db.add(ProcessedEvent(event_id=event_id, event_type=event_type, outcome=outcome, notifications=created))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # a concurrent delivery of the same event won
        return "duplicate"
    return outcome


async def handle_message(envelope: dict[str, Any]) -> None:
    """JetStream entry point. Raising leads to redelivery and finally the DLQ."""
    async with SessionLocal() as db:
        outcome = await process_event(envelope, db=db)
    logger.info("event %s (%s): %s", envelope.get("event_id"), envelope.get("type"), outcome)


def durable_name(event_type: str) -> str:
    return f"{CONSUMER_NAME}-{event_type.replace('.', '-').replace('_', '-')}"


def build_consumers(connection: JetStreamConnection) -> list[DurableConsumer]:
    return [
        DurableConsumer(connection, subject=subject_for(event_type), durable=durable_name(event_type), handler=handle_message)
        for event_type in PLANNERS
    ]
