"""Grant assessment permissions to default user role — assessment.openapi.yaml RBAC."""

revision = "0005_assessment_permissions"
down_revision = "0004_profile_permissions"
branch_labels = None
depends_on = None

_ASSESSMENT_PERMISSIONS = ("assessments:create", "assessments:read", "assessments:write")


def upgrade() -> None:
    from alembic import op

    assessment_perms = ", ".join(f"'{p}'" for p in _ASSESSMENT_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT ARRAY(
                SELECT DISTINCT p
                FROM unnest(
                    COALESCE(permissions, '{{}}'::varchar(128)[])
                    || ARRAY[{assessment_perms}]::varchar(128)[]
                ) AS p
                ORDER BY p
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )


def downgrade() -> None:
    from alembic import op

    assessment_perms = ", ".join(f"'{p}'" for p in _ASSESSMENT_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT COALESCE(
                ARRAY(
                    SELECT p
                    FROM unnest(COALESCE(permissions, '{{}}'::varchar(128)[])) AS p
                    WHERE p NOT IN ({assessment_perms})
                    ORDER BY p
                ),
                '{{}}'::varchar(128)[]
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )
