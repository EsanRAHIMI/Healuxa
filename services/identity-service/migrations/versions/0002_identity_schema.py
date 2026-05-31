"""Identity schema — Healuxa_TechSpec.md §8.4 (Phase 0+ core tables)."""

revision = "0002_identity_schema"
down_revision = "0001_phase0_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op_create = """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(26) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        identifier VARCHAR(320) NOT NULL,
        locale VARCHAR(8),
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_users_tenant_identifier UNIQUE (tenant_id, identifier)
    );
    CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id);

    CREATE TABLE IF NOT EXISTS credentials (
        id VARCHAR(26) PRIMARY KEY,
        user_id VARCHAR(26) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id VARCHAR(26) PRIMARY KEY,
        user_id VARCHAR(26) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        refresh_token_hash VARCHAR(64) NOT NULL,
        previous_refresh_token_hash VARCHAR(64),
        device VARCHAR(255),
        ip VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        revoked_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id);
    CREATE INDEX IF NOT EXISTS ix_sessions_refresh_token_hash ON sessions (refresh_token_hash);

    CREATE TABLE IF NOT EXISTS roles (
        id VARCHAR(26) PRIMARY KEY,
        name VARCHAR(128) NOT NULL,
        tenant_id VARCHAR(64) NOT NULL,
        permissions VARCHAR(128)[] NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_roles_tenant_name UNIQUE (tenant_id, name)
    );
    CREATE INDEX IF NOT EXISTS ix_roles_tenant_id ON roles (tenant_id);

    CREATE TABLE IF NOT EXISTS user_roles (
        user_id VARCHAR(26) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role_id VARCHAR(26) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, role_id)
    );

    CREATE TABLE IF NOT EXISTS jwks_keys (
        kid VARCHAR(64) PRIMARY KEY,
        public_pem TEXT NOT NULL,
        private_pem_enc TEXT NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        rotated_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS service_clients (
        client_id VARCHAR(128) PRIMARY KEY,
        client_secret_hash VARCHAR(64) NOT NULL,
        name VARCHAR(255) NOT NULL,
        scopes VARCHAR(64)[] NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS login_history (
        id VARCHAR(26) PRIMARY KEY,
        user_id VARCHAR(26) REFERENCES users(id) ON DELETE SET NULL,
        identifier VARCHAR(320) NOT NULL,
        success BOOLEAN NOT NULL,
        ip VARCHAR(64),
        reason VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_login_history_created_at ON login_history (created_at);

    CREATE TABLE IF NOT EXISTS idempotency_records (
        key VARCHAR(128) PRIMARY KEY,
        request_hash VARCHAR(64) NOT NULL,
        status_code INTEGER NOT NULL,
        response_body JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    from alembic import op

    op.execute(op_create)

    op.execute(
        """
        INSERT INTO roles (id, name, tenant_id, permissions)
        VALUES
            ('01JROLE00000000000000001', 'user', 'healuxa-dubai', ARRAY['sessions:revoke']),
            ('01JROLE00000000000000002', 'admin', 'healuxa-dubai', ARRAY['iam:read', 'iam:write', 'sessions:revoke'])
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    from alembic import op

    op.execute(
        """
        DROP TABLE IF EXISTS idempotency_records;
        DROP TABLE IF EXISTS login_history;
        DROP TABLE IF EXISTS service_clients;
        DROP TABLE IF EXISTS jwks_keys;
        DROP TABLE IF EXISTS user_roles;
        DROP TABLE IF EXISTS roles;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS credentials;
        DROP TABLE IF EXISTS users;
        """
    )
