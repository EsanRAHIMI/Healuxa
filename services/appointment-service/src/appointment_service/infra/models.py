from __future__ import annotations

from datetime import datetime

from healuxa_py_common.events.outbox_sql import outbox_table
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUSES = (
    "held",
    "requested",
    "confirmed",
    "checked_in",
    "completed",
    "cancelled",
    "declined",
    "no_show",
    "expired",
    "rescheduled",
)
# Statuses that occupy the provider's (and customer's) time. Terminal "freeing" statuses — cancelled,
# declined, expired, rescheduled — release the slot. Past completed/no-show visits keep their time.
BLOCKING_STATUSES = ("held", "requested", "confirmed", "checked_in", "completed", "no_show")
PAYMENT_STATUSES = ("not_required", "pending", "authorized", "captured", "refunded")
PARTIES = ("customer", "provider", "facility", "platform", "system")

_BLOCKING_SQL = "status IN (" + ", ".join(f"'{s}'" for s in BLOCKING_STATUSES) + ")"

PROVIDER_OVERLAP_CONSTRAINT = "ex_appointments_provider_overlap"
CUSTOMER_OVERLAP_CONSTRAINT = "ex_appointments_customer_overlap"
IDEMPOTENCY_INDEX = "uq_appointments_idempotency"
TRANSITION_IDEMPOTENCY_INDEX = "uq_transitions_idempotency"


class Base(DeclarativeBase):
    pass


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointments_range"),
        CheckConstraint("blocked_until >= ends_at", name="ck_appointments_blocked_until"),
        CheckConstraint("status IN (" + ", ".join(f"'{s}'" for s in STATUSES) + ")", name="ck_appointments_status"),
        CheckConstraint(
            "payment_status IN (" + ", ".join(f"'{s}'" for s in PAYMENT_STATUSES) + ")",
            name="ck_appointments_payment_status",
        ),
        # The booking invariant, enforced by PostgreSQL (btree_gist): a provider's holding/active
        # appointments never overlap, visit + buffer included, whatever the application does.
        ExcludeConstraint(
            ("provider_id", "="),
            (text("tstzrange(starts_at, blocked_until, '[)')"), "&&"),
            name=PROVIDER_OVERLAP_CONSTRAINT,
            using="gist",
            where=text(_BLOCKING_SQL),
        ),
        # A customer cannot be in two appointments at once either.
        ExcludeConstraint(
            ("user_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            name=CUSTOMER_OVERLAP_CONSTRAINT,
            using="gist",
            where=text(_BLOCKING_SQL),
        ),
        Index(
            IDEMPOTENCY_INDEX,
            "tenant_id",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_appointments_customer", "tenant_id", "user_id", "starts_at"),
        Index("ix_appointments_provider", "provider_id", "starts_at"),
        Index("ix_appointments_facility", "facility_id", "starts_at"),
        Index("ix_appointments_branch", "branch_id", "starts_at"),
        Index("ix_appointments_expiry", "status", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(26), nullable=False)
    facility_id: Mapped[str] = mapped_column(String(26), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(26), nullable=False)
    service_id: Mapped[str] = mapped_column(String(26), nullable=False)
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # ends_at + the offering's buffer: the provider's time this appointment occupies.
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    service_name: Mapped[str | None] = mapped_column(String(200))
    price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    payment_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="not_required")
    channel: Mapped[str | None] = mapped_column(String(16))
    # held: end of the reservation hold; requested: the answer deadline (= start).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(16))
    decline_reason: Mapped[str | None] = mapped_column(String(32))
    no_show_party: Mapped[str | None] = mapped_column(String(16))
    rescheduled_from_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("appointments.id"))
    rescheduled_to_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("appointments.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AppointmentTransition(Base):
    """Append-only audit trail of every status change: who, when, from, to, why."""

    __tablename__ = "appointment_transitions"
    __table_args__ = (
        CheckConstraint("actor_type IN (" + ", ".join(f"'{p}'" for p in PARTIES) + ")", name="ck_transitions_actor"),
        Index(
            TRANSITION_IDEMPOTENCY_INDEX,
            "appointment_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_transitions_appointment", "appointment_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    appointment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64))
    reason_code: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppointmentReminder(Base):
    """Reminder schedule as data; delivery belongs to notification-service (appointment.reminder_due)."""

    __tablename__ = "appointment_reminders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'dispatched', 'skipped', 'cancelled')", name="ck_reminders_status"
        ),
        Index("uq_reminders_offset", "appointment_id", "offset_minutes", unique=True),
        Index("ix_reminders_due", "status", "due_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    appointment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# Domain events staged in the business transaction; relayed by the outbox relay (py-common).
OUTBOX = outbox_table(Base.metadata)
