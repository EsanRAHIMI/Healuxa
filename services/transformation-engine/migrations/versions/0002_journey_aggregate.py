"""Journey aggregate tables — Healuxa_DDD_Boundaries.md §3.1."""

revision = "0002_journey_aggregate"
down_revision = "0001_phase0_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS journeys (
            id VARCHAR(26) PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(26) NOT NULL,
            primary_goals TEXT[] NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'onboarding',
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            target_completion TIMESTAMPTZ,
            health_index NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
            ltv_projection JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_journeys_tenant_id ON journeys (tenant_id);
        CREATE INDEX IF NOT EXISTS ix_journeys_user_id ON journeys (user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_journeys_active_user
            ON journeys (tenant_id, user_id)
            WHERE status NOT IN ('completed', 'churned');

        CREATE TABLE IF NOT EXISTS goals (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            title VARCHAR(512) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_goals_journey_id ON goals (journey_id);

        CREATE TABLE IF NOT EXISTS phases (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            sequence INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_phases_journey_id ON phases (journey_id);

        CREATE TABLE IF NOT EXISTS milestones (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            phase_id VARCHAR(26) REFERENCES phases(id) ON DELETE SET NULL,
            title VARCHAR(512) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            due_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_milestones_journey_id ON milestones (journey_id);
        CREATE INDEX IF NOT EXISTS ix_milestones_journey_status ON milestones (journey_id, status);

        CREATE TABLE IF NOT EXISTS next_actions (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            action_type VARCHAR(32) NOT NULL,
            priority VARCHAR(16) NOT NULL DEFAULT 'medium',
            due_at TIMESTAMPTZ,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_next_actions_journey_id ON next_actions (journey_id);

        CREATE TABLE IF NOT EXISTS outcome_records (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            milestone_id VARCHAR(26) REFERENCES milestones(id) ON DELETE SET NULL,
            metric_key VARCHAR(128) NOT NULL,
            value NUMERIC(12, 4) NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_outcome_records_journey_id ON outcome_records (journey_id);

        CREATE TABLE IF NOT EXISTS reassessment_triggers (
            id VARCHAR(26) PRIMARY KEY,
            journey_id VARCHAR(26) NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            due_at TIMESTAMPTZ NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            reason VARCHAR(64)
        );
        CREATE INDEX IF NOT EXISTS ix_reassessment_triggers_journey_id ON reassessment_triggers (journey_id);

        CREATE TABLE IF NOT EXISTS idempotency_records (
            key VARCHAR(128) PRIMARY KEY,
            request_hash VARCHAR(64) NOT NULL,
            status_code INTEGER NOT NULL,
            response_body JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade() -> None:
    from alembic import op

    op.execute(
        """
        DROP TABLE IF EXISTS idempotency_records;
        DROP TABLE IF EXISTS reassessment_triggers;
        DROP TABLE IF EXISTS outcome_records;
        DROP TABLE IF EXISTS next_actions;
        DROP TABLE IF EXISTS milestones;
        DROP TABLE IF EXISTS phases;
        DROP TABLE IF EXISTS goals;
        DROP TABLE IF EXISTS journeys;
        """
    )
