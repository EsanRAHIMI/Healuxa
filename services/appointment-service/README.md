# appointment-service (port 8007)

Scheduling context (DDD §3.8), the booking engine: slot derivation from provider-service availability,
reservation holds, booking requests confirmed by the provider side, cancellation, check-in, completion,
no-show, reschedule, an audit trail of every transition, and reminder schedules handed to
notification-service. Contract: `packages/api-contracts/openapi/appointment.openapi.yaml` (v3.4).
Events: `appointment.*` (see `packages/event-contracts/schemas/appointment.schema.json`).
Design notes: `docs/ARCHITECTURE.md` → "Booking".

```bash
scripts/dev/start-infra.sh                     # native Postgres/Redis/NATS/MongoDB (no Docker)
cd services/appointment-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/appointment
alembic upgrade head                           # creates btree_gist + the exclusion constraints
uvicorn appointment_service.main:app --port 8007
```

Runtime dependencies: identity-service (introspection + service token) and provider-service
(`/v1/internal/scheduling/*`). Tests use `appointment_test` and a fake provider directory:
`DATABASE_URL=...appointment_test pytest -q`.

Invariants enforced here:

- **No invented availability.** Slots come only from provider-service facts; if it is unreachable or
  returns garbage, the API answers 503.
- **Exclusive time, enforced by PostgreSQL.** `EXCLUDE USING gist` on `(provider_id, [starts_at,
  blocked_until))` and `(user_id, [starts_at, ends_at))` for holding/active statuses. `blocked_until`
  includes the offering's buffer.
- **No self-confirmation.** `confirmed` requires the provider owner, a facility `facility_admin` /
  `scheduler`, or `appointments:manage`; customers cannot book their own provider's offerings.
- **No health data in events.** Payloads carry ids, times, party and enumerated reason codes; free-text
  reasons stay in the audit table.

Policy is configurable (see `.env.example`): hold TTL, holds per customer, slot grid, lead time,
horizon, customer cancellation/reschedule cut-off, check-in window, no-show grace, reminder offsets,
payment gate.
