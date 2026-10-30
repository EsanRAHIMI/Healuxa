"""Fan-out: one recipient + one template → a notification row and one delivery per channel.

Idempotency: ``source_key`` is the event id (or ``send:<Idempotency-Key>``). Notifications are unique
per (tenant, source_key, user) and deliveries per (tenant, source_key, user, channel); inserts use
ON CONFLICT DO NOTHING, so a redelivered event or a retried request never notifies twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from notification_service.domain import preferences as prefs
from notification_service.domain.templates import get_template, render
from notification_service.infra.models import CHANNELS, Delivery, Notification


@dataclass(frozen=True)
class Recipient:
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class NotifyResult:
    notification_id: str
    created: bool
    deliveries: list[tuple[str, str, str | None]]  # (channel, status, skip_reason)


def now() -> datetime:
    return datetime.now(UTC)


async def notify(
    db: AsyncSession,
    recipient: Recipient,
    *,
    template_key: str,
    params: dict[str, object],
    source_key: str,
    source_event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    channels: tuple[str, ...] | None = None,
    locale: str | None = None,
) -> NotifyResult:
    """Stage a notification in the caller's transaction (the caller commits)."""
    template = get_template(template_key)
    preference = await prefs.load(db, recipient.tenant_id, recipient.user_id)
    use_locale = locale or preference.locale
    title, body = render(template, use_locale, params)
    wanted = tuple(c for c in (channels or template.channels) if c in CHANNELS)

    decisions: dict[str, tuple[bool, str | None]] = {c: preference.allows(template.category, c) for c in wanted}
    at = now()
    notification_id = str(ULID())
    inserted = await db.scalar(
        insert(Notification)
        .values(
            id=notification_id,
            tenant_id=recipient.tenant_id,
            user_id=recipient.user_id,
            category=template.category,
            kind=template.kind,
            template_key=template.key,
            locale=use_locale if use_locale in template.texts else "en",
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            source_key=source_key,
            source_event_type=source_event_type,
            inbox_visible=decisions.get("in_app", (False, None))[0],
            needs_professional_review=template.needs_professional_review,
            created_at=at,
        )
        .on_conflict_do_nothing(constraint="uq_notifications_source_recipient")
        .returning(Notification.id)
    )
    created = inserted is not None
    if not created:
        notification_id = await db.scalar(
            select(Notification.id).where(
                Notification.tenant_id == recipient.tenant_id,
                Notification.source_key == source_key,
                Notification.user_id == recipient.user_id,
            )
        )
    else:
        for channel, (allowed, reason) in decisions.items():
            if not allowed:
                status = "skipped"
            elif channel == "in_app":
                status = "sent"  # the inbox row itself is the delivery
            else:
                status = "pending"
            await db.execute(
                insert(Delivery)
                .values(
                    id=str(ULID()),
                    tenant_id=recipient.tenant_id,
                    notification_id=notification_id,
                    user_id=recipient.user_id,
                    source_key=source_key,
                    channel=channel,
                    status=status,
                    attempts=0,
                    next_attempt_at=at if status == "pending" else None,
                    skip_reason=reason,
                    sent_at=at if status == "sent" else None,
                    created_at=at,
                    updated_at=at,
                )
                .on_conflict_do_nothing(constraint="uq_deliveries_idempotency")
            )
    rows = await db.execute(
        select(Delivery.channel, Delivery.status, Delivery.skip_reason)
        .where(Delivery.notification_id == notification_id)
        .order_by(Delivery.channel)
    )
    return NotifyResult(
        notification_id=notification_id,
        created=created,
        deliveries=[(r.channel, r.status, r.skip_reason) for r in rows],
    )
