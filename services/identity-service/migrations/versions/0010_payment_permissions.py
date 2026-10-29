"""Grant payment-service and subscription-service permissions — payment.openapi / subscription.openapi v3.4.

Customers quote and pay for their own bookings, concierge cases and memberships, and read their own
payments and invoices (ownership enforced in payment-service). Platform admins and the new `finance`
role manage payments (capture/void/disputes), refund, and reconcile. Subscription plans are managed by
admins only.

down_revision: this branch (feat/payment-service) does not contain 0008_appointment_permissions
(feat/appointment-service) or 0009_concierge_permissions (feat/concierge-notifications). The revision
chains onto the highest of those present in this directory, so it is correct on this branch (0007) and
after the merge (0009). At merge time, re-point it to the literal "0009_concierge_permissions" once
0009 itself is chained onto 0008.
"""

from pathlib import Path

_VERSIONS = Path(__file__).resolve().parent
down_revision = next(
    rev
    for rev in ("0009_concierge_permissions", "0008_appointment_permissions", "0007_provider_permissions")
    if (_VERSIONS / f"{rev}.py").exists()
)
revision = "0010_payment_permissions"
branch_labels = None
depends_on = None

_CUSTOMER = (
    "payments:create",
    "payments:read",
    "invoices:read",
    "subscriptions:create",
    "subscriptions:read",
    "subscriptions:write",
)
_FINANCE = ("payments:read", "invoices:read", "payments:manage", "payments:refund", "finance:reconcile")
_GRANTS = {
    "user": _CUSTOMER,
    "admin": (*_CUSTOMER, "payments:manage", "payments:refund", "finance:reconcile", "subscriptions:manage"),
    "finance": _FINANCE,
}
_FINANCE_ROLE_ID = "01JROLEFINANCE000000000010"


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

    op.execute(
        f"""
        INSERT INTO roles (id, name, tenant_id, permissions)
        VALUES ('{_FINANCE_ROLE_ID}', 'finance', 'healuxa-dubai', '{{}}'::varchar(128)[])
        ON CONFLICT (tenant_id, name) DO NOTHING;
        """
    )
    for role, permissions in _GRANTS.items():
        op.execute(_add(role, permissions))


def downgrade() -> None:
    from alembic import op

    for role, permissions in _GRANTS.items():
        if role != "finance":
            op.execute(_remove(role, permissions))
    op.execute(f"DELETE FROM roles WHERE id = '{_FINANCE_ROLE_ID}';")
