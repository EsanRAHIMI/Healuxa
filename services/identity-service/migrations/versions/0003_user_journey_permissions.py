"""Grant journey permissions to default user role — transformation.openapi.yaml RBAC."""

revision = "0003_user_journey_permissions"
down_revision = "0002_identity_schema"
branch_labels = None
depends_on = None

_JOURNEY_PERMISSIONS = ("journeys:create", "journeys:read", "journeys:write")


def upgrade() -> None:
    from alembic import op

    journey_perms = ", ".join(f"'{p}'" for p in _JOURNEY_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT ARRAY(
                SELECT DISTINCT p
                FROM unnest(
                    COALESCE(permissions, '{{}}'::varchar(128)[])
                    || ARRAY[{journey_perms}]::varchar(128)[]
                ) AS p
                ORDER BY p
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )


def downgrade() -> None:
    from alembic import op

    journey_perms = ", ".join(f"'{p}'" for p in _JOURNEY_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT COALESCE(
                ARRAY(
                    SELECT p
                    FROM unnest(COALESCE(permissions, '{{}}'::varchar(128)[])) AS p
                    WHERE p NOT IN ({journey_perms})
                    ORDER BY p
                ),
                '{{}}'::varchar(128)[]
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )
