"""Grant appointment-service permissions — appointment.openapi.yaml v3.4 RBAC.

Every user may book (`appointments:create`), read and act on appointments (`appointments:read`,
`appointments:write`) — appointment-service then restricts them to their own bookings, or to the
practice they own / schedule for (ownership checks use provider-service data). Only platform admins get
`appointments:manage` (tenant-wide operations: book on behalf, act on any appointment).
"""

revision = "0008_appointment_permissions"
down_revision = "0007_provider_permissions"
branch_labels = None
depends_on = None

_GRANTS = {
    "user": ("appointments:create", "appointments:read", "appointments:write"),
    "admin": ("appointments:create", "appointments:read", "appointments:write", "appointments:manage"),
}


def _add(role: str, permissions: tuple[str, ...]) -> str:
    values = ", ".join(f"'{p}'" for p in permissions)
    return f"""
        UPDATE roles
        SET permissions = (
            SELECT ARRAY(
                SELECT DISTINCT p
                FROM unnest(COALESCE(permissions, '{{}}'::varchar(128)[]) || ARRAY[{values}]::varchar(128)[]) AS p
                ORDER BY p
            )
        )
        WHERE name = '{role}' AND tenant_id = 'healuxa-dubai';
    """


def _remove(role: str, permissions: tuple[str, ...]) -> str:
    values = ", ".join(f"'{p}'" for p in permissions)
    return f"""
        UPDATE roles
        SET permissions = COALESCE(
            ARRAY(
                SELECT p FROM unnest(COALESCE(permissions, '{{}}'::varchar(128)[])) AS p
                WHERE p NOT IN ({values}) ORDER BY p
            ),
            '{{}}'::varchar(128)[]
        )
        WHERE name = '{role}' AND tenant_id = 'healuxa-dubai';
    """


def upgrade() -> None:
    from alembic import op

    for role, permissions in _GRANTS.items():
        op.execute(_add(role, permissions))


def downgrade() -> None:
    from alembic import op

    for role, permissions in _GRANTS.items():
        op.execute(_remove(role, permissions))
