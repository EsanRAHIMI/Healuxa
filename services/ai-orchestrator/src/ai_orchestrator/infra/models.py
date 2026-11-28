"""AiSession aggregate (Healuxa_DDD_Boundaries.md §3.18): AiSession → Turn.

Turns hold the conversation text so a session can be resumed; they are personal data, owned by the
user, tenant-scoped and erased on ``auth.user_deleted``. Message text is never written to logs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AiSession(Base):
    __tablename__ = "ai_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    # Concierge case opened by a hand-off in this session (at most one per session).
    handoff_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_ai_sessions_owner", "tenant_id", "user_id", "created_at"),)


class AiTurn(Base):
    __tablename__ = "ai_turns"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(26), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cards: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Which code guardrail shaped this turn, if any: emergency | clinical_redirect | ungrounded | refusal | limit.
    guardrail: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Tool names and outcomes only (no arguments, no results): audit without personal data.
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Client-supplied Idempotency-Key of the user turn; the assistant turn that answered it carries it too.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_ai_turns_session_seq"),
        UniqueConstraint("session_id", "role", "idempotency_key", name="uq_ai_turns_idempotency"),
        Index("ix_ai_turns_rate", "tenant_id", "user_id", "role", "created_at"),
    )
