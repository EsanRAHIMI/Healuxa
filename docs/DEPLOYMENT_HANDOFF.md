# Healuxa — Deployment Handoff (for the Dokploy deployment agent)

This repository is built and tested on a development Mac **without containers**; every container is
built on the Dokploy server (or GitHub runners) from the Dockerfiles below. This document is the
contract between the codebase and the deployment. Nothing here has been deployed yet.

Status words: **Implemented / Tested** apply to code; **Deployed** is your job; nothing is
**Externally approved** or **Published**.

## 1. What to deploy

| Component | Path | Dockerfile (build context = repo root) | Port | Store | Migrations |
|---|---|---|---|---|---|
| identity-service | `services/identity-service` | `services/identity-service/Dockerfile` | 8001 | PostgreSQL `identity`, Redis | `alembic upgrade head` |
| profile-service | `services/profile-service` | `services/profile-service/Dockerfile` | 8002 | MongoDB (replica set / Atlas) | none (indexes ensured at start) |
| assessment-service | `services/assessment-service` | `services/assessment-service/Dockerfile` | 8003 | MongoDB (replica set / Atlas) | none (indexes ensured at start) |
| transformation-engine | `services/transformation-engine` | `services/transformation-engine/Dockerfile` | 8000 | PostgreSQL `transformation` | `alembic upgrade head` |
| provider-service | `services/provider-service` | `services/provider-service/Dockerfile` | 8005 | PostgreSQL `provider` | `alembic upgrade head` |

Further components (appointment-service, web) are added to this table when their branches merge;
check `docs/EXECUTION_LEDGER.md` for the current list before deploying.

Shared infrastructure (Dokploy-managed, **internal network only, never public**): PostgreSQL 16,
Redis 7, NATS 2.x with JetStream (file storage, persistent volume), MongoDB (Atlas or a replica set —
transactions require a replica set). ClickHouse in `infrastructure/docker-compose.dev.yml` is not used
by any service yet; do not deploy it.

## 2. Image facts (verified by `.github/workflows/images.yml` on every push)

- Multi-stage `python:3.12-slim`, runs as **uid 10001** (non-root).
- `PORT` (default above), `WEB_CONCURRENCY` (default 2) and `FORWARDED_ALLOW_IPS` (default `*`;
  narrow to the Traefik subnet) are read at start. uvicorn runs with `--proxy-headers`.
- Docker `HEALTHCHECK` hits `GET /health` (liveness, no dependencies).
- `GET /ready` checks dependencies (DB/Mongo) — use it as the Traefik/Dokploy readiness probe.
- `GET /metrics` exposes Prometheus metrics — **do not route publicly**.
- Images contain `alembic.ini` + `migrations/` where applicable, so migrations run from the same image.

## 3. Release order (per environment: staging first, then production)

1. Provision PostgreSQL databases from `infrastructure/postgres/init-databases.sql` (production needs
   only the non-`_test` databases) with **one login role per service** having rights only on its own DB.
2. Provision Redis, NATS JetStream (persistent volume), MongoDB (Atlas: least-privilege DB users per
   service, IP access list = the server only; region per the residency decision in
   `docs/EXTERNAL_BLOCKERS.md`).
3. Set secrets/env (section 5) per environment. Staging and production must not share any secret.
4. For each service with migrations, run as a **pre-deploy step** in the new image:
   `alembic upgrade head` (working dir `/app/services/<service>` is the image default).
   Rollback: redeploy the previous image; run `alembic downgrade <previous_revision>` only if the
   migration notes allow it (all current migrations round-trip in CI; `0005_event_id_length` in
   transformation refuses to shrink columns that hold UUID event ids — by design).
5. Deploy identity-service first (others introspect tokens against it), then provider, transformation,
   profile, assessment.
6. Probe `/ready` for each; then enable `NATS_ENABLED=true` (relays start publishing any events already
   waiting in the outbox — nothing is lost while it is off).

## 4. Routing (Traefik via Dokploy)

- Public: `api.<domain>/v1/auth/*`, `/.well-known/jwks.json` → identity; `/v1/providers*`,
  `/v1/facilities*`, `/v1/branches*`, `/v1/services*`, `/v1/affiliations*`, `/v1/availability-rules*`
  → provider-service; `/v1/profiles*` → profile; `/v1/assessments*` → assessment; `/v1/journeys*` →
  transformation. Paths follow `packages/api-contracts/openapi/*.yaml`.
- **Never** route `/metrics`, `/v1/auth/introspect`, or service-token endpoints publicly.
- **Strip client-supplied `X-Healuxa-*` headers at the edge** (Traefik `headers.customRequestHeaders`
  set to empty). Leave `HEALUXA_EDGE_SECRET` **unset** until a ForwardAuth integration that sets it is
  built; services then authenticate bearer tokens via identity introspection (current, tested path).
- TLS at Traefik; HSTS on. Rate limiting at the edge (TechSpec Traefik `ratelimit` middleware: average 100,
  burst 50) is recommended; identity also locks accounts after repeated failed logins.

## 5. Environment variables (names only — values are secrets or per-environment)

Common to Python services (`healuxa_py_common.config.ServiceSettings`):
`APP_ENV` (**must be `production` or `staging` on the server** — enables the secret guard below),
`SERVICE_NAME`, `LOG_LEVEL`, `TENANT_DEFAULT`, `NATS_URL`, `NATS_ENABLED`, `REDIS_URL`,
`SERVICE_AUTH_CLIENT_ID`, `SERVICE_AUTH_CLIENT_SECRET`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN`,
`JWT_PUBLIC_JWKS_URL`, `INTERNAL_NETWORK`, `HEALUXA_EDGE_SECRET` (leave unset, see §4).

Per service:
- identity-service: `DATABASE_URL`, `REDIS_URL`, `PASSWORD_PEPPER`, `MFA_ENCRYPTION_KEY` (≥32 bytes),
  `MFA_ISSUER`, `JWT_PRIVATE_KEY_PEM` (optional — otherwise signing keys are generated and stored in the
  DB), `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL`, `JWT_ISSUER`, `ARGON2_MEMORY_COST`, `ARGON2_TIME_COST`,
  `ARGON2_PARALLELISM`, `OTP_TTL`, `LOGIN_MAX_ATTEMPTS`, `LOCKOUT_SECONDS`.
  The `SERVICE_AUTH_CLIENT_ID/SECRET` pair is seeded as the internal mesh client at first start; every
  other service must use the same pair to call introspection.
- provider-service: `DATABASE_URL`, `IDENTITY_INTROSPECT_URL`, `SUPPORTED_CURRENCIES` (JSON list,
  launch `["AED"]`), `PUBLIC_TENANT`.
- transformation-engine: `DATABASE_URL`, `IDENTITY_INTROSPECT_URL` (others listed in its
  `.env.example` are placeholders for future integrations).
- profile-service: `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`,
  `IDENTITY_INTROSPECT_URL`, `MONGODB_CSFLE_KEY_VAULT`, `AWS_KMS_KEY_ID` (CSFLE not yet enabled).
- assessment-service: `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`,
  `IDENTITY_INTROSPECT_URL`.

`DATABASE_URL` format: `postgresql+asyncpg://<role>:<password>@<host>:5432/<db>`.

**Secret guard (tested):** with `APP_ENV=production|staging`, a service refuses to start if any
setting whose name contains `secret`, `pepper`, `encryption_key` or `private_key` is empty or still a
development default; the error names the variables without printing values.

## 6. Data protection prerequisites (do not skip)

- No real patient data until the regulatory items in `docs/EXTERNAL_BLOCKERS.md` are resolved.
- Postgres/Mongo encryption at rest and encrypted backups; daily backups with a tested restore.
- Logs: services log trace ids and event ids, not request bodies. Keep it that way in log shippers.

## 7. Verification after each deploy

- `/ready` = 200 on every service.
- Register → login → `GET /v1/providers/me` (expect 404 for a fresh user) via the public edge.
- Forged-header check: `POST /v1/providers` with only `X-Healuxa-User`/`X-Healuxa-Perms` headers → 401.
- `scripts/smoke/assessment_to_transformation_events.sh` against staging (needs psql access to the
  transformation DB) proves the event path end to end.
