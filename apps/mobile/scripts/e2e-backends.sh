#!/usr/bin/env bash
# Starts the backends the mobile app talks to, natively (no containers), for local runs and E2E:
#   identity :8201, provider :8205, appointment :8207, concierge :8221, notification :8222
# Each uses its own *_mobile_e2e database (created + migrated here). Dev-only values below are not
# secrets; production values come from the deployment environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV="${VENV:-$ROOT/.venv312}"
LOG_DIR="${LOG_DIR:-$ROOT/apps/mobile/e2e/.logs}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
PG="${PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}"
mkdir -p "$LOG_DIR"

export TENANT_DEFAULT=healuxa-dubai PUBLIC_TENANT=healuxa-dubai
export SERVICE_AUTH_CLIENT_ID=healuxa-internal
export SERVICE_AUTH_CLIENT_SECRET="${SERVICE_AUTH_CLIENT_SECRET:-mobile-e2e-service-secret}"
export NATS_ENABLED=false
export IDENTITY_INTROSPECT_URL=http://127.0.0.1:8201/v1/auth/introspect
export IDENTITY_SERVICE_TOKEN_URL=http://127.0.0.1:8201/v1/auth/service-token
export PROVIDER_SERVICE_URL=http://127.0.0.1:8205
export REDIS_URL PASSWORD_PEPPER=mobile-e2e-pepper MFA_ENCRYPTION_KEY=mobile-e2e-mfa-key-32-bytes-long-ok

start() { # name module port db
  local name=$1 module=$2 port=$3 db=$4
  PGPASSWORD=dev "$PG/createdb" -h 127.0.0.1 -U healuxa "$db" 2>/dev/null || true
  (
    cd "$ROOT/services/$name"
    export DATABASE_URL="postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/$db"
    "$VENV/bin/alembic" upgrade head >/dev/null
    nohup "$VENV/bin/uvicorn" "$module:app" --host 0.0.0.0 --port "$port" >"$LOG_DIR/$name.log" 2>&1 &
    echo $! >"$LOG_DIR/$name.pid"
  )
}

start identity-service identity_service.main 8201 identity_mobile_e2e
start provider-service provider_service.main 8205 provider_mobile_e2e
start appointment-service appointment_service.main 8207 appointment_mobile_e2e
start concierge-service concierge_service.main 8221 concierge_mobile_e2e
start notification-service notification_service.main 8222 notification_mobile_e2e

for port in 8201 8205 8207 8221 8222; do
  for _ in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
  curl -fsS "http://127.0.0.1:$port/health" >/dev/null || { echo "backend on :$port is not healthy (see $LOG_DIR)" >&2; exit 1; }
done
echo "mobile backends up on 8201 8205 8207 8221 8222 (logs in $LOG_DIR)"
