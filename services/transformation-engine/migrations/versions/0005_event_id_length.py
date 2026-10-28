"""Accept any contract-valid event_id (ULID or UUID, up to 36 chars) in consumer tables."""

revision = "0005_event_id_length"
down_revision = "0004_outbox_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    for table in ("processed_events", "journey_assessment_links"):
        op.alter_column(table, "event_id", type_=sa.String(36), existing_type=sa.String(26))


def downgrade() -> None:
    import sqlalchemy as sa
    from alembic import op

    # Fails if UUID event ids were stored; that is intentional (no silent truncation).
    for table in ("processed_events", "journey_assessment_links"):
        op.alter_column(table, "event_id", type_=sa.String(26), existing_type=sa.String(36))
