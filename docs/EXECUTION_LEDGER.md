# Healuxa Execution Ledger

Persistent progress record for the Master Production Implementation Directive (v1.0, 2026-10-27).
Status words are used strictly: **Implemented** (code exists), **Tested** (automated tests pass, evidence cited),
**Deployed**, **Externally approved**, **Published**. Nothing below is deployed, approved, or published.

## Status board

Updated 2026-10-29 on `feat/integration`. "Tested" = automated tests pass locally and in CI.

| Stage | Item | Status | Evidence |
|---|---|---|---|
| A | Repository stabilisation (PR #1) | Tested | merged `b1d592f`; CI 40564345781 |
| A | Native local stack (no Docker) | Tested | `scripts/dev/start-infra.sh` (Redis now snapshot-free) |
| A | Transactional outbox, JetStream relay, durable consumers, DLQ | Tested | py-common 23 tests; outage drill |
| A | Envelope wire format matches `envelope.schema.json` | Tested | `a275577`, schema-validation test |
| A | Production secret guard (`APP_ENV=production` refuses dev/empty secrets) | Tested | `test_production_settings.py` |
| — | Forged identity headers rejected (edge secret) | Tested | per-service regression tests |
| — | Hardened images (non-root, healthcheck) built + probed in CI | Tested | Images workflow 40836784227 |
| B | provider-service (providers, credentials, facilities, affiliations, catalog, availability) | Tested | 42 tests |
| C | appointment-service (slots, holds, exclusive-slot DB constraint, lifecycle, reminders) | Tested | 81 tests; CI 40836184672 |
| E | concierge-service (cases, queue, options, secure messaging, escalation, audit) | Tested | 60 tests; CI 40836387378 |
| — | notification-service (inbox, preferences, quiet hours, channels, event consumers) | Tested | 55 tests; CI 40836387378 |
| D | payment-service (quotes, intents, webhooks, refunds, ledger, invoices) | In Progress | agent branch `feat/payment-service` |
| F | Web platform + shared TS packages | In Progress | agent branch `feat/web-platform` |
| G | Mobile app (iOS/Android) | In Progress | agent branch `feat/mobile-app` |
| — | Integration branch (A–E merged) | In Progress | `feat/integration` `07abfd6`; local regression all green |
| — | Deployed / Externally Approved / Published | none | deployment is out of scope for this codebase work |

Known follow-ups:
- notification-service resolves catalog-event recipients from recipient links; provider-service does not
  yet register them, so catalog events are acknowledged as `no_recipient`.
- One unreproduced failure in py-common JetStream integration tests while several agents shared the
  local NATS server; 11 subsequent runs clean. Watch CI.

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

## Session 2026-10-29 — Stage C: appointment-service (booking engine)

Branch `feat/appointment-service` (from `main` 93c6723; not merged). Stage C status: **Tested** (not deployed).

- Contract `appointment.openapi.yaml` 3.4: 7 operations (existing operationIds kept) — `listAvailableSlots`,
  `listAppointments`, `createAppointment` (hold), `getAppointment`, `transitionAppointment`
  (submit/accept/decline/cancel/check_in/complete/no_show), `rescheduleAppointment`,
  `listAppointmentTransitions`. All implemented; routes diffed against the contract by a test.
- Events: existing `appointment.*` payloads gained optional `facility_id`/`branch_id`/`ends_at`; new
  `appointment.cancelled`, `.rescheduled`, `.expired`, `.reminder_due` (registry now 54 events).
- provider-service: service-authenticated `GET /v1/internal/scheduling/services/{id}` and
  `/actors/{user_id}` (`api/internal.py`, documented in `provider.openapi.yaml` with `serviceAuth`).
- Identity migration `0008_appointment_permissions`: users `appointments:create|read|write`, admins also
  `appointments:manage`.
- Design (details in `docs/ARCHITECTURE.md` → Booking): synchronous provider-service reads (503 on failure,
  never invented slots); explicit state machine; reschedule = linked close + create; PostgreSQL
  `btree_gist` exclusion constraints per provider (visit + buffer) and per customer; holds with TTL, lazy
  expiry and a sweeper; reminders as data handed to notification-service by event; `payment_status` hook.
- Tests: appointment-service 81 (pure slot derivation incl. Asia/Dubai and Europe/Berlin both DST
  transitions, buffers, exceptions, hours clipping, effective dates; hold expiry; 10-way parallel holds →
  exactly one 201; raw-SQL overlap rejected by the DB; customer/provider/scheduler/billing/stranger/other
  tenant authorisation; forged headers; idempotent create incl. concurrent retries; audit trail; every
  staged event validated against the JSON Schemas; HTTP client failure modes), provider-service 42
  (37 + 5 internal), identity 33 (31 + 2), contracts valid.
- Found, not fixed (outside Stage C scope): py-common envelopes serialise unset optional fields as `null`
  (`causation_id`, sometimes `trace_id`/`actor`), which `envelope.schema.json` rejects — affects every
  service's events; fix in `outbox_fields` (`exclude_none`) or allow null in the schema.
- Not done: payment-service integration (only the hook), notification delivery, booking UIs, a cached
  read model of catalog data, waitlists, multi-resource bookings (rooms/equipment).


## Payments (feat/payment-service)

Implemented / Tested (sandbox only; nothing deployed, no live keys):

- payment-service (8010): server-side quotes (professional + facility + disclosed platform fee + per-line VAT,
  AED minor units), idempotent payment intents, manual capture (confirm-then-charge), void, full/partial
  refunds with a cancellation-policy hook, disputes, Stripe webhooks (raw-body HMAC, tolerance, event-id
  dedupe, monotonic state machine), double-entry ledger, settlement import, reconciliation report,
  gap-free invoices/credit notes (JSON + HTML), provider/facility settlement reports. Stripe adapter (httpx,
  pinned API version) + deterministic fake processor behind the `PaymentGateway` port. 118 tests.
- subscription-service (8009): plans, memberships, cancel at period end, plan change, entitlements;
  billing state from payment-service events; disabled by `MEMBERSHIPS_ENABLED=false`. No automated tests
  yet (migration round-trip + `alembic check` + import in CI) — next task.
- Contracts: payment.openapi / subscription.openapi 3.4; payment.* / subscription.* events; payment-service
  consumes appointment.* (incl. cancelled/expired/rescheduled) and subscription.created/upgraded/downgraded/
  cancellation_scheduled. Identity `0010_payment_permissions` (after 0009) + `finance` role.

## Mobile app (feat/mobile-app) — `apps/mobile`

Expo SDK 57.0.28 / React Native 0.86.3 (New Architecture, Hermes), Expo Router 57.0.26, TypeScript
strict; every dependency pinned exactly to a release published before 2026-10-14 (SDK 58 still
shipped an RN release candidate at that date, so 57 is the latest stable that qualifies).
`ios/` and `android/` are generated by `expo prebuild` (CNG) locally and in CI, never committed.

| Area | Status | Evidence |
|---|---|---|
| Directory, provider profile (verified credentials, languages, fee breakdown), facility, services | Done — provider-service public reads; offline cache for public content only | `src/api/client.ts`, `src/cache/publicCache.ts` |
| Auth: register, sign in, refresh rotation, sign out, sessions + revoke, biometric unlock | Done — tokens only in Keychain/Keystore | `src/auth/*`, Jest `sessionManager`/`tokenStore` |
| Account deletion | Done — identity `authDeleteAccount` with password re-confirmation | `app/account/delete.tsx` |
| Booking: slots, hold, submit, release, cancel, reschedule, history | Code done against appointment.openapi 3.4 | `app/book/[serviceId].tsx`, `app/appointments/[id].tsx` |
| Concierge: create (non-clinical), options, secure messaging, read receipts, cancel | Done; verified against local concierge-service | `app/concierge/*` |
| Notifications: inbox, unread count, preferences, push token register/delete | Done; verified against local notification-service | `app/notifications.tsx`, `app/account/notifications.tsx`, `src/notifications/push.ts` |
| i18n en/ar/fa + RTL, light/dark, Dynamic Type caps, VoiceOver/TalkBack labels | Done (ar/fa are drafts for a medical translator) | `src/i18n/*` |
| Config | One `EXPO_PUBLIC_API_BASE_URL` (nginx gateway, default `https://api.healuxa.ae`), per-service overrides for local; non-local builds refuse http | `app.config.ts`, CI step |
| Tests | 52 Jest tests (auth flow, secure storage, RTL, fees, errors, cache) pass; Detox smoke written | `src/__tests__`, `e2e/smoke.e2e.js` |
| CI | `mobile` job in ci.yml (lint/typecheck/Jest + https check) and `mobile-builds.yml` (Android bundleRelease on ubuntu, iOS simulator on macos-26) — green on 05646a1 | runs 41089266995, 41089266445 |
| Local builds | iOS sim Debug ✔, iOS sim Release ✔ (90 MB .app), iOS Release generic device `CODE_SIGNING_ALLOWED=NO` and Android `assembleDebug`/`bundleRelease`: see report | `apps/mobile/artifacts/*.log` (not committed) |
| Store readiness | Drafts: metadata, App Privacy, privacy manifest via config, Data Safety, permissions, review notes, deep-link files, `eas.json` | `apps/mobile/store/` |

Blockers / pending (exact):

- **Booking cannot work end-to-end on main today:** appointment-service gets slots from
  provider-service's internal API with an identity service token, but identity `introspect` returns
  `active:false` for service tokens (it looks up `session_id = "svc-<client>"` in the sessions
  table and finds nothing), so provider-service answers 401 and appointment-service 503. The app
  shows "availability cannot be checked" and never invents slots. Fix belongs in identity-service.
- Detox run and data screenshots: the local Postgres lost the `healuxa` role during this session
  (`FATAL: role "healuxa" does not exist`), so the backends could not be restarted; only static
  screens were captured (`store/screenshots/ios/`). Run `scripts/e2e-backends.sh`, `e2e/seed.mjs`,
  then `npx detox test -c ios.sim.release`.
- Shared packages from feat/web-platform (`@healuxa/api-client`, design-tokens, i18n) are not yet on
  main and the generated client lacks appointment v3.4 / concierge / notification; the app keeps its
  local adapter (`src/api/client.ts`, one place to swap) — debt.
- Owner: Apple team id + App ID capabilities (Associated Domains, Push), Android upload keystore
  (`HEALUXA_UPLOAD_*`), FCM `google-services.json` for Android push tokens, APNs key for the push
  driver, store URLs (support/privacy), final brand artwork (icons are generated placeholders).
- Toolchain on this Mac: Homebrew `openjdk@17`, `android-commandlinetools`; SDK (platform-tools,
  android-36, build-tools 36.0.0, NDK pulled by Gradle) under `/Volumes/500GB/Works/healuxa/.mobile-toolchain`
  because the boot volume had < 3 GB free.
