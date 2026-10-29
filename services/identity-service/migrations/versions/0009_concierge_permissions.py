"""Grant concierge-service and notification-service permissions.

Customers may submit and follow their own concierge requests (ownership is enforced in
concierge-service) and manage their own notification inbox, preferences and device tokens.
Platform admins coordinate and supervise concierge cases.

down_revision: ``0008_appointment_permissions`` is being added on feat/appointment-service; until it
exists this migration chains onto 0007. Re-point ``down_revision`` to 0008 when both branches merge.
"""

revision = "0009_concierge_permissions"
down_revision = "0007_provider_permissions"
branch_labels = None
depends_on = None

_GRANTS = {
    "user": ("concierge:request", "notifications:read", "notifications:write"),
    "admin": (
        "concierge:request",
        "concierge:coordinate",
        "concierge:supervise",
        "notifications:read",
        "notifications:write",
    ),
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
