"""AiSession aggregate: sessions and turns of the customer assistant.

Revision ID: 0001_ai_sessions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_ai_sessions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
        sa.Column("handoff_case_id", sa.String(64), nullable=True),
        sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_sessions_owner", "ai_sessions", ["tenant_id", "user_id", "created_at"])
    op.create_table(
        "ai_turns",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("session_id", sa.String(26), sa.ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("cards", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("guardrail", sa.String(32), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("stop_reason", sa.String(32), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "seq", name="uq_ai_turns_session_seq"),
        sa.UniqueConstraint("session_id", "role", "idempotency_key", name="uq_ai_turns_idempotency"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_turns_role"),
    )
    op.create_index("ix_ai_turns_rate", "ai_turns", ["tenant_id", "user_id", "role", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_turns_rate", table_name="ai_turns")
    op.drop_table("ai_turns")
    op.drop_index("ix_ai_sessions_owner", table_name="ai_sessions")
    op.drop_table("ai_sessions")
