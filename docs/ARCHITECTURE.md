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
