# Healuxa Monorepo (v3.3)

Luxury transformation ecosystem — **Phase 0 foundation**. Architecture is frozen; authoritative sources:

1. `Healuxa_TechSpec.md`
2. `Healuxa_DDD_Boundaries.md`
3. `packages/api-contracts` (OpenAPI — HTTP contracts)
4. `packages/event-contracts` (domain events)
5. `.cursor/rules/architecture-governance.mdc`

## Local development model

| Layer | How you run it |
|--------|----------------|
| **Infrastructure** | Docker Compose (`infrastructure/docker-compose.dev.yml`): PostgreSQL 16, Redis 7, NATS JetStream, ClickHouse, optional Traefik for local edge |
| **Application services** | From your laptop (Python venv, Uvicorn) — recommended for `identity-service` |
| **MongoDB Atlas, S3/CloudFront** | External only — configure via environment variables (no local Mongo/S3 containers) |

**Production / staging** is deployed with **Dokploy** (Traefik, TLS, domains). Migrations are a **controlled pre-deploy step** (`alembic upgrade head`), not an implicit production startup side effect.

## Prerequisites

- **Node.js** ≥ 22 (`npm install` at repo root)
- **Python** 3.12 (matches CI and Docker images; avoid 3.14+ for parity)
- **Docker** + Docker Compose v2
- Optional: `psql` client for manual DB checks

## 1. Install dependencies

```bash
cd /path/to/healuxa/apps
npm install

python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e packages/py-common
pip install -e "services/identity-service[dev]"
```

## 2. Start local infrastructure (Docker Compose)

```bash
cd infrastructure
docker compose -f docker-compose.dev.yml up -d postgres redis nats clickhouse
```

Wait until Postgres is healthy:

```bash
docker compose -f docker-compose.dev.yml ps
```

Optional — full stack including Traefik and identity in Docker (after migrations, see below):

```bash
docker compose -f docker-compose.dev.yml --profile app up -d
```

Traefik (local only): `http://api.localhost` → identity routes when the `app` profile is enabled. Production routing is owned by **Dokploy**.

## 3. Configure environment

```bash
cp services/identity-service/.env.example services/identity-service/.env
```

Edit `.env` for **laptop execution** (defaults target `localhost`). See `.env.example` for Docker Compose hostnames (`postgres`, `redis`, `nats`) and Dokploy production values.

## 4. Run database migrations (identity)

**Always run before first start or after pulling new migrations.** Uses the `identity` logical database (TechSpec §8).

```bash
source .venv/bin/activate
cd services/identity-service
alembic upgrade head
```

**Docker Compose helper (dev only)** — one-shot migrate container:

```bash
cd infrastructure
docker compose -f docker-compose.dev.yml --profile migrate run --rm identity-migrate
```

**Dokploy / production:** run the same `alembic upgrade head` in your deploy pipeline **before** switching traffic to the new image (rolling deploy per service).

## 5. Run identity-service locally (laptop)

```bash
source .venv/bin/activate
cd services/identity-service
uvicorn identity_service.main:app --host 0.0.0.0 --port 8001 --reload
```

Verify:

```bash
curl -s http://localhost:8001/health
curl -s http://localhost:8001/ready
```

## 6. Run tests

Tests use the separate database **`identity_test`** so they do not touch your development `identity` data.

Ensure infrastructure is up, then:

```bash
# Create test DB once (if not created by postgres init)
docker exec healuxa-dev-postgres-1 psql -U healuxa -d postgres -c "CREATE DATABASE identity_test;" 2>/dev/null || true

source .venv/bin/activate
cd services/identity-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@localhost:5432/identity_test
export REDIS_URL=redis://localhost:6379/15
export PASSWORD_PEPPER=dev-pepper-change-me
export MFA_ENCRYPTION_KEY=dev-mfa-key-32bytes-long!!!!!!
export SERVICE_AUTH_CLIENT_ID=healuxa-internal
export SERVICE_AUTH_CLIENT_SECRET=dev-service-secret-change-me
alembic upgrade head
pytest -q
```

From repo root (after `npm install`):

```bash
npm run ci:python
npm run ci:contracts
```

## 7. Validate contracts

```bash
npm run contracts:validate
# or
npm run ci:contracts
```

## 8. Dokploy deployment (identity-service)

1. Create a Dokploy application pointing at this monorepo path: `services/identity-service`.
2. Build: **Dockerfile** (`services/identity-service/Dockerfile`, context = repo root) or **Nixpacks** (`nixpacks.toml` in the service folder).
3. Port: **8001**.
4. Set environment variables from `services/identity-service/.env.example` (production URLs, secrets, managed Postgres/Redis/NATS).
5. **Pre-deploy:** `alembic upgrade head` against the production `identity` DSN (Dokploy pre-deploy command or CI job).
6. Health check path: `/health` (readiness: `/ready`).

Do not rely on automatic migrations at container start in production.

## 9. Run transformation-engine locally (laptop)

```bash
source .venv/bin/activate
cd services/transformation-engine
uvicorn transformation_engine.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

API base path: `/v1/journeys/*`. In development, send Traefik-style principal headers (see `transformation_engine.api.deps.principal_headers`) or a Bearer token introspected via identity-service.

### transformation-engine tests

Tests use **`transformation_test`** (separate from dev `transformation` data).

```bash
docker exec healuxa-dev-postgres-1 psql -U healuxa -d postgres -c "CREATE DATABASE transformation_test;" 2>/dev/null || true

source .venv/bin/activate
cd services/transformation-engine
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@localhost:5432/transformation_test
export TENANT_DEFAULT=healuxa-dubai
alembic upgrade head
pytest -q
```

### Dokploy (transformation-engine)

1. Application path: `services/transformation-engine`.
2. Build: **Dockerfile** (context = repo root) or **Nixpacks** (`nixpacks.toml`).
3. Port: **8000**.
4. Environment: `services/transformation-engine/.env.example`.
5. **Pre-deploy:** `alembic upgrade head` on production `transformation` DSN.
6. Health: `/health`, readiness: `/ready`.

## 10. E2E smoke (Identity → Transformation)

Standalone script that exercises **real HTTP** between running services (no mocks, no DB access from the script).

**Prerequisites**

1. Infrastructure: `docker compose -f infrastructure/docker-compose.dev.yml up -d` (Postgres + Redis).
2. Migrations on **dev** databases (not `_test`):
   - `services/identity-service` → `identity` (must include `0003_user_journey_permissions`)
   - `services/transformation-engine` → `transformation`
3. Both apps running on the laptop:
   - identity-service on **8001**
   - transformation-engine on **8000**
4. Matching service credentials on transformation (`SERVICE_AUTH_CLIENT_*` same as identity seed).
5. Tools: `curl`, `jq`.

**Run from repo root**

```bash
chmod +x scripts/smoke/identity_to_transformation.sh
./scripts/smoke/identity_to_transformation.sh
```

Optional overrides:

```bash
export IDENTITY_URL=http://localhost:8001
export TRANSFORMATION_URL=http://localhost:8000
export SERVICE_AUTH_CLIENT_ID=healuxa-internal
export SERVICE_AUTH_CLIENT_SECRET=dev-service-secret-change-me
./scripts/smoke/identity_to_transformation.sh
```

**Flow:** `POST /v1/auth/register` → `POST /v1/auth/introspect` (assert `journeys:*`) → `POST /v1/journeys` with `Authorization: Bearer` → `GET /v1/journeys/{userId}`.

Exit code `0` on success; non-zero with a clear error on failure. Each run uses a unique email (no truncation).

## Repository layout (Phase 0–1)

```
apps/                          # this repo root
├── packages/
│   ├── api-contracts/
│   ├── event-contracts/
│   ├── py-common/
│   └── ts-common/
├── services/
│   ├── identity-service/
│   └── transformation-engine/
├── infrastructure/
│   └── docker-compose.dev.yml
└── .github/workflows/ci.yml
```
