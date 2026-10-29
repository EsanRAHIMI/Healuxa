# notification-service (port 8022)

Multi-channel notifications (DDD §3.18). Contract: `packages/api-contracts/openapi/notification.openapi.yaml`
(v3.4). Publishes no events; consumes (JetStream `DurableConsumer`s, started when `NATS_ENABLED=true`):

| Event | Recipient | Template |
|---|---|---|
| `concierge.case_status_changed` | case customer (+ coordinator when assigned) | `concierge.case_status_changed`, `concierge.case_assigned` |
| `concierge.message_posted` | the counterparty of the sender (never the text) | `concierge.message_posted` |
| `catalog.provider_status_changed` | users linked to the provider | `catalog.provider_status_changed` |
| `catalog.affiliation_changed` | users linked to the provider and facility | `catalog.affiliation_changed` |
| `appointment.requested/created/accepted/declined/completed/no_show` (+ `cancelled/rescheduled/expired/reminder_due`, registered on the appointment-service branch) | `payload.user_id` | `appointment.*` |

```bash
scripts/dev/start-infra.sh                     # native Postgres/Redis/NATS/MongoDB (no Docker)
cd services/notification-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/notification
alembic upgrade head
uvicorn notification_service.main:app --port 8022
```

Tests use `notification_test`: `DATABASE_URL=...notification_test NATS_URL=nats://127.0.0.1:4222 pytest -q`
(without `NATS_URL` the three JetStream tests are skipped; CI always sets it).

## Model

- **Recipient resolution without health data.** Events carry ids only. Catalog events have no owner
  id, so services register *recipient links* (`POST /v1/notifications/recipient-links`, service
  auth: entity → user). Unresolvable events are acknowledged with outcome `no_recipient`.
- **Templates** (`domain/templates.py`) render en/ar/fa from declared parameters only (enum labels,
  timestamps); unknown parameters are rejected. Arabic/Persian strings are drafts awaiting native
  review; legal/policy wording is flagged `needs_professional_review` and carried onto notifications.
- **Idempotency.** `processed_events` per `event_id`; notifications unique per (tenant, source, user),
  deliveries per (tenant, source, user, channel). Direct sends use `send:<Idempotency-Key>`.
- **Channels** behind `channels/base.py::ChannelDriver`: in-app inbox (the notification row), email,
  SMS, WhatsApp, push. Default driver `log` records the attempt and sends nothing; `disabled` skips.
  `smtp` is the only real driver and needs `ALLOW_REAL_DELIVERY=true` plus a `ContactResolver`
  (none integrated yet — addresses are not stored here). Other providers plug in via `REAL_DRIVERS`.
- **Delivery worker:** pending → sent | skipped | dead_letter; retries with exponential backoff
  (`DELIVERY_BACKOFF_BASE_SECONDS`·2ⁿ, capped), dead-letter after `DELIVERY_MAX_ATTEMPTS` or a
  permanent error. Preferences are re-checked at send time.
- **Preferences:** per-category channel switches, locale, IANA time zone, quiet hours (push/SMS/
  WhatsApp deferred to the end of the window; inbox and email are not), marketing consent (off by
  default; categories `concierge`, `appointments`, `provider_account`, `account` are transactional).
- **Device tokens:** `POST/DELETE /v1/notification-devices` — tokens are stored, never returned.

Malformed events raise `PoisonEvent`, are retried by the consumer and finally dead-lettered to
`HEALUXA_DLQ`.
