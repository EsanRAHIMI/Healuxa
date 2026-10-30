from __future__ import annotations

from datetime import datetime
from typing import Any

from healuxa_py_common.events.outbox_sql import outbox_table
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SUBSCRIPTION_STATUSES = ("incomplete", "active", "past_due", "paused", "cancelled", "expired")
OPEN_STATUSES = ("incomplete", "active", "past_due", "paused")


class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("billing_cycle IN ('monthly', 'quarterly', 'annual')", name="ck_plans_cycle"),
        CheckConstraint("status IN ('active', 'retired')", name="ck_plans_status"),
        CheckConstraint("price_minor >= 100", name="ck_plans_price"),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    credits: Mapped[int | None] = mapped_column(Integer)
    entitlements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("status IN (" + ", ".join(f"'{s}'" for s in SUBSCRIPTION_STATUSES) + ")", name="ck_subscriptions_status"),
        UniqueConstraint("tenant_id", "user_id", "creation_key", name="uq_subscriptions_creation_key"),
        # At most one open membership per customer.
        Index(
            "uq_subscriptions_one_open",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('incomplete', 'active', 'past_due', 'paused')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="incomplete")
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    credits_remaining: Mapped[int | None] = mapped_column(Integer)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConsumedEvent(Base):
    __tablename__ = "consumed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


OUTBOX = outbox_table(Base.metadata)
