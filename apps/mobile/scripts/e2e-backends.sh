#!/usr/bin/env bash
# Starts identity-service (8201) and provider-service (8205) natively for mobile E2E runs.
# Requires: a Python venv with the services installed (see apps/mobile/README.md), Postgres 16 on
# 127.0.0.1:5432 with databases identity_mobile_e2e / provider_mobile_e2e migrated, and Redis.
# Dev-only values below are not secrets; production values come from the deployment environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV="${VENV:-$ROOT/.venv312}"
LOG_DIR="${LOG_DIR:-$ROOT/apps/mobile/e2e/.logs}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
mkdir -p "$LOG_DIR"

export TENANT_DEFAULT=healuxa-dubai
export SERVICE_AUTH_CLIENT_ID=healuxa-internal
export SERVICE_AUTH_CLIENT_SECRET="${SERVICE_AUTH_CLIENT_SECRET:-mobile-e2e-service-secret}"
export NATS_ENABLED=false

(
  cd "$ROOT/services/identity-service"
  DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/identity_mobile_e2e \
  REDIS_URL="$REDIS_URL" \
  PASSWORD_PEPPER=mobile-e2e-pepper \
  MFA_ENCRYPTION_KEY=mobile-e2e-mfa-key-32-bytes-long-ok \
  "$VENV/bin/alembic" upgrade head >/dev/null
  DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/identity_mobile_e2e \
  REDIS_URL="$REDIS_URL" \
  PASSWORD_PEPPER=mobile-e2e-pepper \
  MFA_ENCRYPTION_KEY=mobile-e2e-mfa-key-32-bytes-long-ok \
  nohup "$VENV/bin/uvicorn" identity_service.main:app --host 0.0.0.0 --port 8201 >"$LOG_DIR/identity.log" 2>&1 &
  echo $! >"$LOG_DIR/identity.pid"
)

(
  cd "$ROOT/services/provider-service"
  DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/provider_mobile_e2e \
  "$VENV/bin/alembic" upgrade head >/dev/null
  DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/provider_mobile_e2e \
  IDENTITY_INTROSPECT_URL=http://127.0.0.1:8201/v1/auth/introspect \
  nohup "$VENV/bin/uvicorn" provider_service.main:app --host 0.0.0.0 --port 8205 >"$LOG_DIR/provider.log" 2>&1 &
  echo $! >"$LOG_DIR/provider.pid"
)

for url in http://127.0.0.1:8201/health http://127.0.0.1:8205/health; do
  for _ in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && break
    sleep 0.5
  done
  curl -fsS "$url" >/dev/null || { echo "backend not healthy: $url" >&2; exit 1; }
done
echo "identity-service :8201 and provider-service :8205 are up (logs in $LOG_DIR)"
