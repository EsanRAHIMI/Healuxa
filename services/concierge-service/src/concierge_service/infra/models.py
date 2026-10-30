from __future__ import annotations

from datetime import date, datetime

from healuxa_py_common.events.outbox_sql import outbox_table
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CASE_STATUSES = (
    "submitted",
    "triaged",
    "assigned",
    "in_progress",
    "awaiting_customer",
    "arranged",
    "completed",
    "cancelled",
    "escalated",
)
CASE_CATEGORIES = (
    "medical_travel",
    "specialist_search",
    "second_opinion_coordination",
    "logistics",
    "other",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Base(DeclarativeBase):
    pass


class ConciergeCase(Base):
    __tablename__ = "concierge_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", "creation_key", name="uq_cases_creation_key"),
        CheckConstraint(_in("status", CASE_STATUSES), name="ck_cases_status"),
        CheckConstraint(_in("category", CASE_CATEGORIES), name="ck_cases_category"),
        CheckConstraint(
            "preferred_end_date IS NULL OR preferred_start_date IS NULL OR preferred_end_date >= preferred_start_date",
            name="ck_cases_dates",
        ),
        Index("ix_cases_customer", "tenant_id", "customer_id", "created_at"),
        Index("ix_cases_queue", "tenant_id", "status", "created_at"),
        Index("ix_cases_coordinator", "tenant_id", "coordinator_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    preferred_start_date: Mapped[date | None] = mapped_column(Date)
    preferred_end_date: Mapped[date | None] = mapped_column(Date)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False)
    destination_city: Mapped[str | None] = mapped_column(String(120))
    # Explicitly non-clinical logistics needs; never copied into events.
    needs_note: Mapped[str | None] = mapped_column(Text)
    coordinator_id: Mapped[str | None] = mapped_column(String(36))
    selected_option_id: Mapped[str | None] = mapped_column(String(26))
    escalated_from: Mapped[str | None] = mapped_column(String(24))
    first_response_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creation_key: Mapped[str | None] = mapped_column(String(128))
    creation_hash: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CaseAudit(Base):
    """Append-only audit trail: every transition, assignment and option decision."""

    __tablename__ = "case_audit"
    __table_args__ = (Index("ix_case_audit_case", "case_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(26), ForeignKey("concierge_cases.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    subject_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InternalNote(Base):
    __tablename__ = "internal_notes"
    __table_args__ = (Index("ix_internal_notes_case", "case_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(26), ForeignKey("concierge_cases.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderOption(Base):
    """A provider-service reference proposed to the customer; no provider data is copied here."""

    __tablename__ = "provider_options"
    __table_args__ = (
        UniqueConstraint("case_id", "provider_id", "branch_id", "service_id", name="uq_provider_options_ref"),
        CheckConstraint(_in("status", ("proposed", "selected", "not_selected")), name="ck_provider_options_status"),
        Index("ix_provider_options_case", "case_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(26), ForeignKey("concierge_cases.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    facility_id: Mapped[str | None] = mapped_column(String(36))
    branch_id: Mapped[str | None] = mapped_column(String(36))
    service_id: Mapped[str | None] = mapped_column(String(36))
    label: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CaseMessage(Base):
    __tablename__ = "case_messages"
    __table_args__ = (
        CheckConstraint(_in("sender_role", ("customer", "coordinator")), name="ck_case_messages_sender_role"),
        Index("ix_case_messages_case", "case_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(26), ForeignKey("concierge_cases.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


OUTBOX = outbox_table(Base.metadata)
