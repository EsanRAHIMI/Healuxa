from __future__ import annotations

from datetime import date, datetime
from typing import Any

from healuxa_py_common.events.outbox_sql import outbox_table
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PROVIDER_STATUSES = ("pending", "active", "suspended", "offboarded")
VERIFICATION_STATUSES = ("unverified", "under_review", "verified", "rejected")
OPEN_AFFILIATION_STATUSES = ("pending", "active")


class Base(DeclarativeBase):
    pass


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_providers_tenant_user"),
        Index("ix_providers_directory", "tenant_id", "status", "verification_status"),
        Index("ix_providers_specialties", "specialties", postgresql_using="gin"),
        Index("ix_providers_languages", "languages", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str | None] = mapped_column(String(160))
    bio: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    specialties: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unverified")
    quality_score: Mapped[float | None] = mapped_column(Float)
    success_score: Mapped[float | None] = mapped_column(Float)
    creation_key: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "kind", "issuing_authority", "number", name="uq_credentials_provider_identity"
        ),
        CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_credentials_dates"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(64), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(16))
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    document_ref: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="submitted")
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "license_authority", "license_number", name="uq_facilities_license"),
        Index("ix_facilities_directory", "tenant_id", "status", "verification_status"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    license_authority: Mapped[str] = mapped_column(String(64), nullable=False)
    license_number: Mapped[str] = mapped_column(String(64), nullable=False)
    website: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unverified")
    review_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    creation_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    facility_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    emirate: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FacilityStaff(Base):
    __tablename__ = "facility_staff"

    facility_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Affiliation(Base):
    __tablename__ = "affiliations"
    __table_args__ = (
        # One open (pending/active) affiliation per provider and branch, enforced by the database.
        Index(
            "uq_affiliations_open",
            "provider_id",
            "branch_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    facility_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(26), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    initiated_by: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(36))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceOffering(Base):
    __tablename__ = "service_offerings"
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 5 AND 720", name="ck_offerings_duration"),
        CheckConstraint("buffer_minutes BETWEEN 0 AND 240", name="ck_offerings_buffer"),
        CheckConstraint(
            "(price_type = 'on_request' AND professional_fee_minor IS NULL AND facility_fee_minor IS NULL)"
            " OR (price_type IN ('fixed', 'from') AND professional_fee_minor >= 0 AND facility_fee_minor >= 0)",
            name="ck_offerings_price",
        ),
        Index("ix_offerings_catalog", "tenant_id", "status", "category"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    facility_id: Mapped[str] = mapped_column(String(26), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(26), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="in_person")
    price_type: Mapped[str] = mapped_column(String(16), nullable=False)
    professional_fee_minor: Mapped[int | None] = mapped_column(Integer)
    facility_fee_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="AED")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperatingHoursWindow(Base):
    """Branch opening hours in branch-local minutes since midnight (end may be 1440 = 24:00)."""

    __tablename__ = "operating_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_hours_weekday"),
        CheckConstraint("start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute", name="ck_hours_range"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    branch_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_rules_weekday"),
        CheckConstraint("start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute", name="ck_rules_range"),
        CheckConstraint("effective_until IS NULL OR effective_until >= effective_from", name="ck_rules_dates"),
        Index("ix_rules_provider_weekday", "provider_id", "weekday"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(26), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(26), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_exceptions_range"),
        Index("ix_exceptions_provider_range", "provider_id", "starts_at", "ends_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(26), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("branches.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Domain events staged in the business transaction; relayed by the outbox relay (py-common).
OUTBOX = outbox_table(Base.metadata)
