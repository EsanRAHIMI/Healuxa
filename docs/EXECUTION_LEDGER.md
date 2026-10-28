# Healuxa Execution Ledger

Persistent progress record for the Master Production Implementation Directive (v1.0, 2026-10-27).
Status words are used strictly: **Implemented** (code exists), **Tested** (automated tests pass, evidence cited),
**Deployed**, **Externally approved**, **Published**. Nothing below is deployed, approved, or published.

## Session 2026-10-27 — Phase 1 (repository stabilization)

### Audit baseline

- `main` @ `aeaae9d` (2026-06-14). Last CI run `33627147087` (2026-09-02): failed in
  `profile-service` and `assessment-service`; all other jobs green.
- Local constraint from the owner: **no Docker** for local development. Native processes only.

### Capability matrix (verified against the repository, not the spec)

| Bounded context | OpenAPI contract | Service code | Tests |
|---|---|---|---|
| Identity & access | yes | `services/identity-service` (Postgres, Redis, Alembic 0001–0005) | CI green 2026-09-02; not run locally (no native Postgres/Redis) |
| Customer profiles | yes | `services/profile-service` (MongoDB) | 6 pass locally |
| Assessment | yes | `services/assessment-service` (MongoDB) | 8 pass locally |
| Transformation / journeys | yes | `services/transformation-engine` (Postgres, assessment.completed consumer) | CI green 2026-09-02; not run locally |
| Appointment, payment, provider, marketplace, matching, notification, review, subscription, commercial, CRM, marketing, media, medication, treatment, ML, AI, provider-success | yes (contract only) | **none** | — |
| Web, portals, admin console, iOS, Android | — | **none** | — |

Shared packages: `py-common` (4 tests pass), `ts-common` (3 pass), `event-contracts` (3 pass),
`api-contracts` (Redocly lint: valid, 1 warning).

### CI failure root cause (`RuntimeError: Event loop is closed`)

Reproduced locally by pointing the tests at an unreachable MongoDB:

1. The first Mongo test fails with `ServerSelectionTimeoutError` (in CI: the Atlas test cluster was not
   reachable from the GitHub runner — IP access list, paused cluster, or rotated secret).
2. The autouse reset fixture created a module-global Motor client on that test's event loop and never
   closed it when setup failed or when a test did not request the `client` fixture.
3. pytest-asyncio gives each test a fresh loop, so every later test reused the stale client and raised
   `Event loop is closed`, masking the real cause.

Fixes (Tested):

- Migrated both services from Motor (end-of-life, superseded by PyMongo's native asyncio API) to
  `pymongo.AsyncMongoClient`; `close_client()` now always drops the global reference and awaits close.
- Autouse fixtures yield and close the client in `finally`, so no loop-bound client survives a test.
- `MONGODB_SERVER_SELECTION_TIMEOUT_MS` setting (default 10 s) so unreachable databases fail fast.
- CI no longer depends on an Atlas secret: `scripts/ci/install-mongodb.sh` installs MongoDB 8.0 natively
  on the runner and `scripts/dev/start-mongodb.sh` starts a single-node replica set (same topology class
  as Atlas). The jobs now fail loudly if `MONGODB_URI` is missing instead of silently skipping.
- Bumped `actions/checkout@v5`, `setup-python@v6`, `setup-node@v5` (Node 20 runtime deprecation).

Evidence (local, Python 3.12.12, pymongo 4.19, pytest 9.1.1, pytest-asyncio 1.4.1):

- Healthy replica set: profile 6/6, assessment 8/8 pass.
- Unreachable server: every Mongo test reports `ServerSelectionTimeoutError`; zero `Event loop is closed`.
- The new CI workflow has **not** run yet — it runs on the next push.

### Known failures / gaps

- identity-service and transformation-engine not validated locally (need native Postgres 16 + Redis 7,
  e.g. `brew install postgresql@16 redis`).
- No appointment, payment, provider, or facility services exist; no client applications exist.
- Assessment → transformation event path relies on NATS; no transactional outbox in the Mongo services.

### External blockers

- GitHub CLI not authenticated on this machine (`gh auth login`) — needed to read CI logs and open PRs.
- Payment processor merchant account, DHA/legal role determination, Apple/Google developer accounts,
  UAE hosting decision — all owner actions, none started.

### Next executable tasks (dependency order)

1. Push the stabilization branch; confirm CI green.
2. Native local Postgres/Redis; run identity + transformation suites locally.
3. Transactional outbox for profile/assessment event publishing.
4. Provider & facility management service (verification workflow, no hardcoded provider data).
5. Availability + appointment service with exclusive-slot concurrency control and hold expiry.
6. Payment service behind a processor-agnostic port (sandbox only until merchant account exists).
7. Next.js public web + customer portal; Expo app — after the booking API exists.
