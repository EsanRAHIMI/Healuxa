from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


TERMINAL_JOURNEY_STATUSES = ("completed", "churned")


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    primary_goals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="onboarding")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    target_completion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_index: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("1.000"))
    ltv_projection: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    phase_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("phases.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NextAction(Base):
    __tablename__ = "next_actions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutcomeRecord(Base):
    __tablename__ = "outcome_records"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    milestone_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("milestones.id", ondelete="SET NULL"))
    metric_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReassessmentTrigger(Base):
    __tablename__ = "reassessment_triggers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    journey_id: Mapped[str] = mapped_column(String(26), ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(String(64))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
