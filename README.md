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

## 11. E2E smoke (Identity → Profile)

Exercises **real HTTP** with a Bearer token only on profile-service (no `X-Healuxa-*`, no Mongo access from the script).

**Prerequisites:** Postgres + Redis (compose), identity on **8001** (`alembic upgrade head` including `0004_profile_permissions`), profile-service on **8002** with Atlas `MONGODB_URI` in `.env`, `curl`, `jq`.

```bash
chmod +x scripts/smoke/identity_to_profile.sh
./scripts/smoke/identity_to_profile.sh
```

Optional overrides: `IDENTITY_URL`, `PROFILE_URL`, `SERVICE_AUTH_CLIENT_ID`, `SERVICE_AUTH_CLIENT_SECRET`.

**Flow:** register → introspect (`profiles:read`, `profiles:write`) → `GET` 404 → `PUT` 200 + ETag → `GET` 200. No database cleanup.

## 12. Run profile-service locally (laptop)

**MongoDB Atlas only** — do not add MongoDB to `docker-compose.dev.yml`. Set `MONGODB_URI` in `.env` from your Atlas dev cluster.

```bash
source .venv/bin/activate
cd services/profile-service
cp .env.example .env   # edit MONGODB_URI and MONGODB_DATABASE
uvicorn profile_service.main:app --host 0.0.0.0 --port 8002 --reload
```

Verify:

```bash
curl -s http://localhost:8002/health
curl -s http://localhost:8002/ready
```

API: `GET` / `PUT` `/v1/profiles/{userId}`. Bearer token introspected via identity-service (or `X-Healuxa-*` headers in mesh).

### profile-service tests (Atlas test database)

Tests require `MONGODB_URI` and **`MONGODB_DATABASE=healuxa_profile_test`** (name must contain `test`). Destructive cleanup (`delete_many`) runs **only** when the database name contains `test`.

```bash
export MONGODB_URI='mongodb+srv://...'
export MONGODB_DATABASE=healuxa_profile_test
cd services/profile-service
pip install -e ../../packages/py-common
pip install -e ".[dev]"
pytest -q
```

Without `MONGODB_URI`, Mongo tests are **skipped** (exit 0). CI uses GitHub secret `MONGODB_URI_TEST` when configured.

Identity must include `profiles:read` and `profiles:write` on the default `user` role (`alembic upgrade head` in identity-service, migration `0004_profile_permissions`).

## 13. Run assessment-service locally (laptop)

**MongoDB Atlas only** — do not add MongoDB to `docker-compose.dev.yml`. Set `MONGODB_URI` in `.env` from your Atlas dev cluster.

```bash
source .venv/bin/activate
cd services/assessment-service
cp .env.example .env   # edit MONGODB_URI and MONGODB_DATABASE
uvicorn assessment_service.main:app --host 0.0.0.0 --port 8003 --reload
```

Verify:

```bash
curl -s http://localhost:8003/health
curl -s http://localhost:8003/ready
```

API: `POST` / `GET` / `POST .../submit` under `/v1/assessments`. Bearer token introspected via identity-service (or `X-Healuxa-*` headers in mesh).

The scaffold stores submitted assessment responses only. It does not generate recommendations, scores, diagnosis, or roadmap inputs yet. After submit, `recommended_goals=[]` and `scores={}` until a later approved phase.

`Idempotency-Key` is optional per `assessment.openapi.yaml` on `POST /v1/assessments` and `POST /v1/assessments/{id}/submit`; the service implements replay-safe idempotency for those endpoints.

### assessment-service tests (Atlas test database)

Tests require `MONGODB_URI` and **`MONGODB_DATABASE=healuxa_assessment_test`** (name must contain `test`). Destructive cleanup (`delete_many`) runs **only** when the database name contains `test`.

```bash
export MONGODB_URI='mongodb+srv://...'
export MONGODB_DATABASE=healuxa_assessment_test
cd services/assessment-service
pip install -e ../../packages/py-common
pip install -e ".[dev]"
pytest -q
```

Without `MONGODB_URI`, Mongo tests are **skipped** (exit 0). CI uses GitHub secret `MONGODB_URI_TEST` when configured.

Identity must include `assessments:create`, `assessments:read`, and `assessments:write` on the default `user` role (`alembic upgrade head`, migration `0005_assessment_permissions`).

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
│   ├── transformation-engine/
│   ├── profile-service/
│   └── assessment-service/
├── infrastructure/
│   └── docker-compose.dev.yml
└── .github/workflows/ci.yml
```
(.venv) ehsanrahimi@Esan-4 transformation-engine % >....            

export DATABASE_URL=postgresql+asyncpg://healuxa:dev@localhost:5432/transformation
export TENANT_DEFAULT=healuxa-dubai
export IDENTITY_INTROSPECT_URL=http://localhost:8001/v1/auth/introspect
export SERVICE_AUTH_CLIENT_ID=healuxa-internal
export SERVICE_AUTH_CLIENT_SECRET=dev-service-secret-change-me
export NATS_ENABLED=false

uvicorn transformation_engine.main:app --host 0.0.0.0 --port 8000 --reload

