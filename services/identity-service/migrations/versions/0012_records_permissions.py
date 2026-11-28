"""Grant medical-records permissions — profile.openapi.yaml v3.5.

Every customer manages their own records and consent grants (`records:manage`; profile-service limits
them to their own documents). Every user may also read records *shared with an organisation they belong
to* (`records:read_shared`): practitioners and facility staff are ordinary `user` accounts, and the
permission alone grants nothing — profile-service additionally requires an active grant naming that
organisation and verifies membership with provider-service on every read.

Platform admins get no records permission beyond their own customer account: there is no implicit
staff access to medical documents.

Chains after 0010_payment_permissions.
"""

down_revision = "0011_ai_permissions"
revision = "0012_records_permissions"
branch_labels = None
depends_on = None

_GRANTS = {
    "user": ("records:manage", "records:read_shared"),
    "admin": ("records:manage", "records:read_shared"),
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
