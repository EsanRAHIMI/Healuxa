from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CHANNELS = ("in_app", "email", "sms", "whatsapp", "push")
DELIVERY_STATUSES = ("pending", "sent", "skipped", "dead_letter")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Base(DeclarativeBase):
    pass


class Notification(Base):
    """One rendered notification for one recipient. ``source_key`` is the event id (or a direct-send
    idempotency key), so a redelivered event can never notify the same user twice."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_key", "user_id", name="uq_notifications_source_recipient"),
        Index("ix_notifications_inbox", "tenant_id", "user_id", "created_at"),
        Index(
            "ix_notifications_unread",
            "tenant_id",
            "user_id",
            postgresql_where=text("read_at IS NULL AND inbox_visible"),
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_event_type: Mapped[str | None] = mapped_column(String(128))
    inbox_visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    needs_professional_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Delivery(Base):
    """One channel attempt series for a notification: pending → sent | skipped | dead_letter."""

    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_key", "user_id", "channel", name="uq_deliveries_idempotency"),
        CheckConstraint(_in("channel", CHANNELS), name="ck_deliveries_channel"),
        CheckConstraint(_in("status", DELIVERY_STATUSES), name="ck_deliveries_status"),
        Index("ix_deliveries_due", "status", "next_attempt_at"),
        Index("ix_deliveries_notification", "notification_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    notification_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deferred_reason: Mapped[str | None] = mapped_column(String(32))
    skip_reason: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Preference(Base):
    __tablename__ = "preferences"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    locale: Mapped[str | None] = mapped_column(String(8))
    timezone: Mapped[str | None] = mapped_column(String(64))
    quiet_start: Mapped[time | None] = mapped_column(Time)
    quiet_end: Mapped[time | None] = mapped_column(Time)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    marketing_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {category: {channel: bool}} — only explicit user choices; defaults live in code.
    channels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("tenant_id", "token", name="uq_device_tokens_token"),
        CheckConstraint(_in("platform", ("ios", "android", "web")), name="ck_device_tokens_platform"),
        Index("ix_device_tokens_user", "tenant_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecipientLink(Base):
    """Who is notified about an entity whose events carry no user id (e.g. a provider's owner)."""

    __tablename__ = "recipient_links"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    notifications: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
