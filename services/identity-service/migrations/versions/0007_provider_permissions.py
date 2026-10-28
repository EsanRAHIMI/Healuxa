"""Grant provider-service permissions — provider.openapi.yaml v3.4 RBAC.

Customers may apply as a provider or register a facility (ownership checks happen in
provider-service). Only platform admins may verify credentials, facilities and change status.
"""

revision = "0007_provider_permissions"
down_revision = "0006_outbox_events"
branch_labels = None
depends_on = None

_GRANTS = {
    "user": ("providers:onboard", "facilities:onboard"),
    "admin": ("providers:onboard", "facilities:onboard", "providers:verify", "facilities:verify"),
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
