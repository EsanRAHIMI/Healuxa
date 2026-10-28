# Healuxa Execution Ledger

Persistent progress record for the Master Production Implementation Directive (v1.0, 2026-10-27).
Status words are used strictly: **Implemented** (code exists), **Tested** (automated tests pass, evidence cited),
**Deployed**, **Externally approved**, **Published**. Nothing below is deployed, approved, or published.

## Status board

| Stage | Item | Status | Evidence |
|---|---|---|---|
| A | PR #1 stabilization merged | Tested | `b1d592f`, CI run 40564345781 (7/7) |
| A | Native local stack (no Docker) | Tested | `scripts/dev/start-infra.sh` |
| A | Transactional outbox (Postgres + Mongo) | Tested | py-common + service tests; branch `feat/reliable-events` |
| A | Durable JetStream consumers, retry, DLQ | Tested | `test_events_integration.py` |
| A | Idempotent consumer (transformation) | Tested | redelivery test, live smoke |
| A | Correlation/trace propagation through events | Tested | envelope + outbox tests |
| A | Consistent service configuration | In Progress | `NATS_ENABLED`/`NATS_URL` shared; per-service settings not yet unified |
| — | Security: forged identity headers rejected | Tested | branch `fix/edge-header-trust`, CI 40706171858 |
| B | Provider & facility service (API, migrations, RBAC) | Tested | branch `feat/provider-service`; 37 tests; live smoke |
| B | Provider/facility portal UIs | Not Started | — |
| C | Booking engine | Not Started | — |
| D | Payments | Not Started | — |
| E | Concierge operations | Not Started | — |
| F | Web applications | Not Started | — |
| G | Mobile applications | Not Started | — |
| — | Deployed / Externally Approved / Published | none | — |

## Session 2026-10-28 (cont.) — security fix and Stage B provider-service

- **Critical auth bypass fixed** (`fix/edge-header-trust`): services trusted `X-Healuxa-User/-Perms`
  headers from any caller. They are now honoured only with a matching `X-Healuxa-Edge-Secret`; otherwise
  bearer introspection applies. Unit tests + per-service regression tests; CI run 40706171858 green.
- **provider-service** (`feat/provider-service`, builds on both branches above):
  - Contract `provider.openapi.yaml` 3.4 (34 operations) and `catalog.*` events (registry now 50 events).
  - PostgreSQL schema with DB-enforced invariants (unique license per facility, one open affiliation per
    provider/branch, fee and time-range checks); migration round-trips and `alembic check` reports no drift.
  - All 34 contract operations implemented (verified by diffing generated OpenAPI against the contract).
  - Identity migration `0007_provider_permissions`: users get `providers:onboard`, `facilities:onboard`;
    admins additionally `providers:verify`, `facilities:verify`.
  - Tests: provider-service 37, identity 31 — covering verification/activation rules, public visibility
    and field redaction, idempotent onboarding, If-Match, staff roles and last-admin protection, the
    affiliation handshake, fee breakdown, AED-only currency, opening-hours and cross-branch overlap
    rules, a 5-way concurrent overlapping-rule race (exactly one wins), forged headers, tenant isolation.
  - Live smoke: identity token → provider-service via introspection: create 201, self-activation 403,
    forged headers 401 (logged), anonymous directory empty until verification.
  - Not done in Stage B yet: credential document upload (needs object storage), provider/facility portal
    UIs, admin verification UI, appointment-service slot derivation (Stage C).

## Session 2026-10-28 — Stage A: reliable events

Work on branch `feat/reliable-events` (not yet merged).

- **Before:** every service did fire-and-forget core-NATS publishes on a fresh connection, swallowed all
  errors and logged "published" — a broker hiccup silently lost the event. Nothing subscribed to
  `assessment.completed`; the consumer existed only as a function called by tests.
- **Now:** events are staged in an `outbox_events` table/collection inside the business transaction and
  relayed to JetStream (`HEALUXA_EVENTS`, `Nats-Msg-Id` dedup). transformation-engine runs a durable pull
  consumer with explicit acks, backoff, `max_deliver=5`, and a dead-letter stream (`HEALUXA_DLQ`).
- Defects found and fixed along the way:
  - **Cross-service contract bug:** envelopes used UUIDv4 event ids (36 chars) but transformation stored
    `event_id` as `VARCHAR(26)` — every real `assessment.completed` would have failed. Envelopes now emit
    ULIDs and consumer columns accept the full contract range (migration `0005_event_id_length`).
  - **Double completion race:** concurrent submits could both complete an assessment and both emit
    `assessment.completed`; completion is now a guarded single-winner transactional update.
  - **Post-commit publishes** in identity `register` and refresh-token-reuse moved inside the transaction.
  - Concurrent first-time profile create now returns 409 instead of an unhandled duplicate-key error.
  - Relay backoff overflowed after ~30 failed attempts; capped.
- Evidence (local, native stack): py-common 16, identity 29, transformation 21, profile 8, assessment 12 —
  all pass; contracts valid; migrations round-trip (downgrade base → upgrade head).
- Live smoke (`scripts/smoke/assessment_to_transformation_events.sh`) with three running services: PASS.
  Outage drill: NATS stopped mid-flow → event held in outbox (`outbox_pending: 1`) → NATS restarted →
  delivered and consumed (`outbox_pending: 0`).
- CI now provisions native NATS (checksum-verified v2.15.1) and MongoDB, plus a Postgres service container
  for py-common; jobs fail if a backend is missing rather than skipping.

### Next executable tasks

1. Open PRs for `feat/reliable-events`, `fix/edge-header-trust`, `feat/provider-service` and merge after review.
   - Follow-up: operator DLQ replay command (`healuxa-events replay`), currently manual.
2. Stage C: appointment-service — slot derivation from `catalog` rules/hours/exceptions, holds with
   expiry, exclusive-slot constraint, confirmation states, reschedule/cancel/no-show.

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

- GitHub CLI not authenticated on this machine (`gh auth login`) — see `docs/EXTERNAL_BLOCKERS.md`.
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
