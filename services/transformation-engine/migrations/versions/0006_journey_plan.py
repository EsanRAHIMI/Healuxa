"""Journey plan: goal-driven phases and steps, with appointment linkage on milestones."""

revision = "0006_journey_plan"
down_revision = "0005_event_id_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    # Additive and nullable/defaulted only: existing rows stay valid and old code keeps working.
    op.execute(
        """
        ALTER TABLE phases ADD COLUMN IF NOT EXISTS code VARCHAR(32);
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS code VARCHAR(32);
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS goal VARCHAR(64);
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS service_category VARCHAR(80);
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS sequence INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS appointment_id VARCHAR(36);
        ALTER TABLE milestones ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ;
        CREATE INDEX IF NOT EXISTS ix_milestones_appointment_id
            ON milestones (appointment_id) WHERE appointment_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    from alembic import op

    op.execute(
        """
        DROP INDEX IF EXISTS ix_milestones_appointment_id;
        ALTER TABLE milestones DROP COLUMN IF EXISTS scheduled_at;
        ALTER TABLE milestones DROP COLUMN IF EXISTS appointment_id;
        ALTER TABLE milestones DROP COLUMN IF EXISTS sequence;
        ALTER TABLE milestones DROP COLUMN IF EXISTS service_category;
        ALTER TABLE milestones DROP COLUMN IF EXISTS goal;
        ALTER TABLE milestones DROP COLUMN IF EXISTS code;
        ALTER TABLE phases DROP COLUMN IF EXISTS code;
        """
    )
