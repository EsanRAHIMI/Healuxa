"""Grant profile permissions to default user role — profile.openapi.yaml RBAC."""

revision = "0004_profile_permissions"
down_revision = "0003_user_journey_permissions"
branch_labels = None
depends_on = None

_PROFILE_PERMISSIONS = ("profiles:read", "profiles:write")


def upgrade() -> None:
    from alembic import op

    profile_perms = ", ".join(f"'{p}'" for p in _PROFILE_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT ARRAY(
                SELECT DISTINCT p
                FROM unnest(
                    COALESCE(permissions, '{{}}'::varchar(128)[])
                    || ARRAY[{profile_perms}]::varchar(128)[]
                ) AS p
                ORDER BY p
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )


def downgrade() -> None:
    from alembic import op

    profile_perms = ", ".join(f"'{p}'" for p in _PROFILE_PERMISSIONS)
    op.execute(
        f"""
        UPDATE roles
        SET permissions = (
            SELECT COALESCE(
                ARRAY(
                    SELECT p
                    FROM unnest(COALESCE(permissions, '{{}}'::varchar(128)[])) AS p
                    WHERE p NOT IN ({profile_perms})
                    ORDER BY p
                ),
                '{{}}'::varchar(128)[]
            )
        )
        WHERE name = 'user' AND tenant_id = 'healuxa-dubai';
        """
    )
