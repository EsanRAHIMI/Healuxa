"""Internal tables for assessment.completed consumption (Phase 1 — link/audit only)."""

revision = "0003_assessment_integration"
down_revision = "0002_journey_aggregate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id VARCHAR(26) PRIMARY KEY,
            event_type VARCHAR(64) NOT NULL,
            consumer VARCHAR(64) NOT NULL,
            tenant_id VARCHAR(64) NOT NULL,
            outcome VARCHAR(32) NOT NULL,
            detail VARCHAR(512),
            processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_processed_events_type_processed
            ON processed_events (event_type, processed_at);

        CREATE TABLE IF NOT EXISTS journey_assessment_links (
            id VARCHAR(26) PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            assessment_id VARCHAR(26) NOT NULL,
            event_id VARCHAR(26) NOT NULL UNIQUE,
            assessment_kind VARCHAR(32) NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL,
            link_status VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_journey_assessment_links_tenant_assessment
                UNIQUE (tenant_id, assessment_id)
        );
        CREATE INDEX IF NOT EXISTS ix_journey_assessment_links_journey_id
            ON journey_assessment_links (journey_id);
        """
    )


def downgrade() -> None:
    from alembic import op

    op.execute(
        """
        DROP TABLE IF EXISTS journey_assessment_links;
        DROP TABLE IF EXISTS processed_events;
        """
    )
