from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from transformation_engine.infra.models import Base

CONSUMER_NAME = "transformation-engine"

OUTCOME_ACKED = "acked"
OUTCOME_SKIPPED = "skipped"
OUTCOME_REJECTED = "rejected"

LINK_STATUS_PENDING_ROADMAP_SEED = "pending_roadmap_seed"


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    # Envelope contract: ULID or UUID (16-36 chars).
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(512))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JourneyAssessmentLink(Base):
    __tablename__ = "journey_assessment_links"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    journey_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("journeys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[str] = mapped_column(String(26), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    assessment_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    link_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
