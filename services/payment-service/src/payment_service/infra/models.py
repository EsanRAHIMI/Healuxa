"""payment-service schema. Card data is never stored: only processor object ids (pi_/re_/ch_/dp_/cus_/sub_)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from healuxa_py_common.events.outbox_sql import outbox_table
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PAYMENT_STATUSES = ("pending", "processing", "authorized", "succeeded", "failed", "canceled", "partially_refunded", "refunded")
REFUND_STATUSES = ("pending", "succeeded", "failed", "canceled")
LEDGER_ACCOUNTS = (
    "processor_clearing",
    "provider_revenue",
    "facility_revenue",
    "healuxa_revenue",
    "vat_payable",
    "processor_fees",
    "disputes",
    "bank",
    "suspense",
)


class Base(DeclarativeBase):
    pass


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint(_in("subject_type", ("appointment", "concierge_case", "membership")), name="ck_quotes_subject_type"),
        CheckConstraint("total_minor = subtotal_minor + tax_minor", name="ck_quotes_total"),
        CheckConstraint("total_minor > 0", name="ck_quotes_positive"),
        Index("ix_quotes_subject", "tenant_id", "subject_type", "subject_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(36))
    facility_id: Mapped[str | None] = mapped_column(String(36))
    service_id: Mapped[str | None] = mapped_column(String(36))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(_in("status", PAYMENT_STATUSES), name="ck_payments_status"),
        CheckConstraint(_in("capture_method", ("automatic", "manual")), name="ck_payments_capture_method"),
        CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        CheckConstraint("amount_captured_minor >= 0 AND amount_refunded_minor >= 0 AND amount_refund_pending_minor >= 0", name="ck_payments_non_negative"),
        # The database itself refuses refunding more than was captured, whatever the application does.
        CheckConstraint(
            "amount_refunded_minor + amount_refund_pending_minor <= amount_captured_minor", name="ck_payments_refund_limit"
        ),
        UniqueConstraint("processor", "processor_payment_id", name="uq_payments_processor_id"),
        Index("ix_payments_user", "tenant_id", "user_id", "created_at"),
        Index("ix_payments_subject", "tenant_id", "subject_type", "subject_id"),
        Index("ix_payments_charge", "processor_charge_id"),
        Index("uq_payments_quote", "quote_id", unique=True, postgresql_where=text("quote_id IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quote_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("quotes.id"))
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(36))
    facility_id: Mapped[str | None] = mapped_column(String(36))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_authorized_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    amount_captured_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    amount_refunded_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    amount_refund_pending_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    capture_method: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    processor: Mapped[str] = mapped_column(String(32), nullable=False)
    processor_payment_id: Mapped[str | None] = mapped_column(String(255))
    processor_charge_id: Mapped[str | None] = mapped_column(String(255))
    processor_status: Mapped[str | None] = mapped_column(String(64))
    processor_subscription_id: Mapped[str | None] = mapped_column(String(255))
    billing_reason: Mapped[str] = mapped_column(String(32), nullable=False, server_default="one_off")
    billing_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    cancel_reason: Mapped[str | None] = mapped_column(String(64))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(_in("status", REFUND_STATUSES), name="ck_refunds_status"),
        CheckConstraint("amount_minor > 0", name="ck_refunds_amount_positive"),
        UniqueConstraint("payment_id", "idempotency_key", name="uq_refunds_idempotency"),
        UniqueConstraint("processor_refund_id", name="uq_refunds_processor_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(26), ForeignKey("payments.id"), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    processor_refund_id: Mapped[str | None] = mapped_column(String(255))
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dispute(Base):
    __tablename__ = "disputes"
    __table_args__ = (UniqueConstraint("processor", "processor_dispute_id", name="uq_disputes_processor_id"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(26), ForeignKey("payments.id"), nullable=False, index=True)
    processor: Mapped[str] = mapped_column(String(32), nullable=False)
    processor_dispute_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    funds_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    evidence_due_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcessorEvent(Base):
    """Every verified webhook event id, so redeliveries and replays are processed exactly once."""

    __tablename__ = "processor_events"
    __table_args__ = (UniqueConstraint("processor", "event_id", name="uq_processor_events_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    processor: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConsumedEvent(Base):
    __tablename__ = "consumed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "operation", "key", name="uq_idempotency_scope"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(26), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LedgerJournal(Base):
    __tablename__ = "ledger_journals"
    __table_args__ = (
        CheckConstraint(_in("kind", ("capture", "refund", "processor_fee", "payout", "dispute", "dispute_reversal")), name="ck_ledger_journals_kind"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Natural key ("capture:<payment>", "refund:<refund>", "fee:<txn>") makes every posting idempotent.
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("payments.id"), index=True)
    refund_id: Mapped[str | None] = mapped_column(String(26))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(_in("account", LEDGER_ACCOUNTS), name="ck_ledger_entries_account"),
        CheckConstraint(
            "(debit_minor > 0 AND credit_minor = 0) OR (credit_minor > 0 AND debit_minor = 0)", name="ck_ledger_entries_one_side"
        ),
        Index("ix_ledger_entries_payee", "tenant_id", "payee_type", "payee_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    journal_id: Mapped[str] = mapped_column(String(26), ForeignKey("ledger_journals.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(String(26), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    account: Mapped[str] = mapped_column(String(32), nullable=False)
    line_code: Mapped[str | None] = mapped_column(String(64))
    payee_type: Mapped[str | None] = mapped_column(String(16))
    payee_id: Mapped[str | None] = mapped_column(String(36))
    debit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    credit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BalanceTransaction(Base):
    """Processor balance transactions (charges, refunds, fees, payouts) imported for reconciliation."""

    __tablename__ = "balance_transactions"
    __table_args__ = (
        UniqueConstraint("processor", "processor_txn_id", name="uq_balance_transactions_id"),
        Index("ix_balance_transactions_created", "tenant_id", "created"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    processor: Mapped[str] = mapped_column(String(32), nullable=False)
    processor_txn_id: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), index=True)
    payout_id: Mapped[str | None] = mapped_column(String(255), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvoiceSequence(Base):
    """One row per tenant and series; the row lock makes numbering gap-free and concurrency-safe."""

    __tablename__ = "invoice_sequences"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    series: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(_in("kind", ("invoice", "credit_note")), name="ck_invoices_kind"),
        UniqueConstraint("tenant_id", "series", "sequence", name="uq_invoices_sequence"),
        UniqueConstraint("tenant_id", "number", name="uq_invoices_number"),
        Index("uq_invoices_payment_invoice", "payment_id", unique=True, postgresql_where=text("kind = 'invoice'")),
        Index("uq_invoices_refund_credit_note", "refund_id", unique=True, postgresql_where=text("refund_id IS NOT NULL")),
        Index("ix_invoices_user", "tenant_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    series: Mapped[str] = mapped_column(String(8), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(26), ForeignKey("payments.id"), nullable=False)
    refund_id: Mapped[str | None] = mapped_column(String(26))
    original_invoice_id: Mapped[str | None] = mapped_column(String(26))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seller: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PayeeMember(Base):
    __tablename__ = "payee_members"
    __table_args__ = (UniqueConstraint("tenant_id", "payee_type", "payee_id", "user_id", name="uq_payee_members"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payee_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payee_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcessorCustomer(Base):
    __tablename__ = "processor_customers"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "processor", name="uq_processor_customers_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    processor: Mapped[str] = mapped_column(String(32), nullable=False)
    processor_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AppointmentView(Base):
    """Read model of appointment-service bookings (from appointment.* events)."""

    __tablename__ = "appointment_views"

    appointment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    service_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MembershipView(Base):
    """Read model of subscription-service memberships plus the processor subscription owned here."""

    __tablename__ = "membership_views"

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    lines: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    processor_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    processor_item_id: Mapped[str | None] = mapped_column(String(255))
    processor_status: Mapped[str | None] = mapped_column(String(32))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processor_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


OUTBOX = outbox_table(Base.metadata)
