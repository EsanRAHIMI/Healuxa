# Healuxa Architecture (as built)

Authoritative design: `Healuxa_TechSpec.md`, `Healuxa_DDD_Boundaries.md`, `packages/api-contracts`,
`packages/event-contracts`. This file records how the running system actually works.

## Services

| Service | Store | Publishes | Consumes |
|---|---|---|---|
| identity-service | PostgreSQL, Redis | `auth.user_registered`, `auth.session_revoked`, `auth.security_event` | — |
| profile-service | MongoDB | `profile.updated` | — |
| assessment-service | MongoDB | `assessment.completed` | — |
| transformation-engine | PostgreSQL | `journey.*` | `assessment.completed` |
| provider-service | PostgreSQL | `catalog.*` (provider/facility status, affiliations, availability) | — |
| concierge-service | PostgreSQL | `concierge.case_submitted`, `concierge.case_status_changed`, `concierge.message_posted` (ids only) | — |
| notification-service | PostgreSQL | — | `concierge.case_status_changed`, `concierge.message_posted`, `catalog.provider_status_changed`, `catalog.affiliation_changed`, `appointment.*` |

## Authentication at service boundaries

Services accept the edge-injected `X-Healuxa-*` identity headers **only** when the request also carries
`X-Healuxa-Edge-Secret` matching `HEALUXA_EDGE_SECRET`. Otherwise those headers are ignored and the bearer
token is introspected against identity-service. The Traefik ForwardAuth integration that would set the
secret is not built yet, so production must leave `HEALUXA_EDGE_SECRET` unset until it is.

## Event delivery

```
business transaction ──► outbox_events (same transaction) ──► OutboxRelay ──► JetStream HEALUXA_EVENTS
                                                                              │
                                     DurableConsumer (pull, explicit ack) ◄───┘
                                       ├─ success → ack
                                       ├─ failure → nak with backoff (1s, 5s, 30s, 120s)
                                       └─ delivery ≥ max_deliver → copy to HEALUXA_DLQ, term
```

- **Atomicity:** an event exists only if its business change committed (Postgres transaction, or a MongoDB
  multi-document transaction — MongoDB must run as a replica set; Atlas always does).
- **At-least-once:** relays lease rows (`FOR UPDATE SKIP LOCKED` / atomic `find_one_and_update`), so several
  replicas can run safely. A crash between publish and mark-published republishes; JetStream's
  `Nats-Msg-Id` window (10 min) drops the duplicate.
- **Idempotent consumers:** handlers key on `event_id` (transformation: `processed_events`).
- **Subjects:** `healuxa.<context>.<name>.v<version>`; DLQ: `healuxa_dlq.<context>.<name>.v<version>`
  with headers `Healuxa-Dlq-Reason`, `Healuxa-Dlq-Consumer`, `Healuxa-Original-Subject`.
- **Event ids:** ULIDs. The contract accepts ULID or UUID (16–36 chars); consumers must store 36.
- **Tracing:** envelopes inherit the request trace id as `trace_id` and default `correlation_id`;
  consumers bind it for logging.
- **Switch:** relays and consumers start only when `NATS_ENABLED=true`. With NATS disabled, events still
  accumulate in the outbox and are delivered once a relay runs — nothing is dropped.

Code: `packages/py-common/src/healuxa_py_common/events/`.

## Booking (appointment-service, Stage C)

| Service | Store | Publishes | Consumes |
|---|---|---|---|
| appointment-service (8007) | PostgreSQL (`appointment`) | `appointment.*` | — (reads provider-service synchronously) |

**Availability source: synchronous read from provider-service, no local copy.** appointment-service calls
`GET /v1/internal/scheduling/services/{id}` (offering duration/buffer, provider/facility/branch status,
branch IANA zone, opening hours, the provider's rules at that branch, exceptions in a window) and
`GET /v1/internal/scheduling/actors/{user_id}` (owned providers, facility staff roles) with a service
token from identity (`POST /v1/auth/service-token`, cached until shortly before expiry, refreshed once on
401). Timeouts are short (`PROVIDER_TIMEOUT_SECONDS`, default 3 s). Any failure — unreachable, non-200,
malformed body, invalid zone — answers **503**; the engine never derives slots from missing data and
authorisation lookups fail closed. Chosen over an event-fed read model because it is always current
(no lag window in which a suspended provider stays bookable) and is easy to test through the injectable
`ProviderDirectory` protocol. The `catalog.*` events remain available if a cache/read model is added later.

**Slot derivation** (`domain/slots.py`, pure): for each branch-local date, windows = rules (weekday,
effective dates) ∩ opening hours; bounds become UTC instants in the branch zone; candidates step every
`SLOT_INTERVAL_MINUTES` from the window start; a slot is offered if the visit fits the window and its
occupancy `[start, start + duration + buffer)` overlaps no exception and no holding/active booking
(whose occupancy includes its own buffer). Lead time and horizon bound the result. DST: a spring-forward
gap has no slots, a fall-back hour is offered twice; Asia/Dubai has no DST. Responses carry UTC instants,
the zone and local ISO times.

**State machine**

```
held ─submit─► requested ─accept─► confirmed ─check_in─► checked_in ─complete─► completed
 │               │ └─decline─► declined   │ ├─complete─► completed
 ├─TTL─► expired ├─start passed─► expired  │ ├─no_show─► no_show
 └─cancel─► cancelled └─cancel─► cancelled └─cancel─► cancelled
requested|confirmed ─reschedule─► rescheduled  (+ new appointment, rescheduled_from_id/rescheduled_to_id)
```

- `confirmed` only via `accept` by the provider owner, a facility `facility_admin`/`scheduler`, or
  `appointments:manage`, and only while the offering is still bookable and payment is not pending.
- Reschedule = close the original (`rescheduled`) and create a linked appointment in one transaction. A
  customer reschedule needs re-confirmation (`requested`); a practice-side reschedule is `confirmed`.
- Customer cancel/reschedule of a confirmed booking is allowed until `CUSTOMER_CANCEL_CUTOFF_MINUTES`
  before the start; the practice may cancel until the start. Check-in opens `CHECK_IN_OPENS_MINUTES`
  before the start; `complete` needs the start to have passed; `no_show` needs `NO_SHOW_GRACE_MINUTES`
  (provider no-shows only by `appointments:manage`).
- Every change is appended to `appointment_transitions` (from, to, actor type/id, reason code, free-text
  reason, time). Transitions and creates accept `Idempotency-Key`; transitions also `If-Match`.
- `payment_status` (`not_required|pending|authorized|captured|refunded`) is the Stage D hook: with
  `PAYMENT_REQUIRED=true`, priced bookings start `pending` and cannot be accepted until a payment
  consumer sets them `authorized`/`captured` (not built yet).

**Exclusive slots are a database invariant.** Migration `0001_appointment_schema` enables `btree_gist` and
adds `EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, blocked_until, '[)') WITH &&)` and the
same on `(user_id, tstzrange(starts_at, ends_at))`, both `WHERE status IN (held, requested, confirmed,
checked_in, completed, no_show)`. The application pre-check only produces friendlier errors; under
concurrency PostgreSQL decides (a deadlock victim among competing exclusion inserts is reported as 409).
Holds expire lazily (reads ignore/expire stale holds) and via the sweeper task.

**Reminders.** On confirmation, rows are written for each `REMINDER_OFFSETS_MINUTES` (default 24 h and 2 h;
already-past ones `skipped`). The sweeper (`SWEEPER_INTERVAL_SECONDS`, `FOR UPDATE SKIP LOCKED`, safe with
replicas) emits `appointment.reminder_due` via the outbox and marks rows `dispatched`; cancelled or
started appointments never get one. **Delivery (channel, template, locale, quiet hours, retries) belongs
to the future notification-service**, which consumes `appointment.reminder_due` idempotently by
`reminder_id`.

**Events** (outbox, `healuxa.appointment.<name>.v1`): `requested` (submit), `accepted` + `created`
(confirmation; `created` = a confirmed appointment exists, also after a practice reschedule), `declined`,
`cancelled` (not for released holds), `rescheduled`, `expired` (unanswered request), `completed`,
`no_show`, `reminder_due`. Payloads hold ids, times, party and enumerated reasons only — no health data,
no free text.
