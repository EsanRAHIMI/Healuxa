# Operations

## Local development (macOS, native — no Docker)

```bash
brew install postgresql@16 redis nats-server mongodb-community
scripts/dev/start-infra.sh   # Postgres :5432, Redis :6379, NATS JetStream :4222, MongoDB rs0 :27020
scripts/dev/stop-infra.sh
```

Data lives in `.local/` (git-ignored). Never point local runs at production databases.

## Event health

- `GET /ready` on Mongo services reports `outbox_pending`; a steadily growing value means the relay
  cannot reach NATS.
- Prometheus: `healuxa_outbox_published_total`, `healuxa_outbox_publish_failures_total`,
  `healuxa_events_consumed_total{outcome="acked|retried|dead_lettered"}`.
- Alert on any `dead_lettered` increase and on `outbox_pending` > 0 for more than 5 minutes.

## Dead-letter handling

Exhausted events land in the `HEALUXA_DLQ` stream with `Healuxa-Dlq-Reason`, `Healuxa-Dlq-Consumer`,
`Healuxa-Dlq-Deliveries` and `Healuxa-Original-Subject` headers (verified by
`packages/py-common/tests/test_events_integration.py`).

A supported replay command is **not built yet** (tracked in the execution ledger). Until then, replay is
a manual operator action: republish the stored body to `Healuxa-Original-Subject`. Consumers are
idempotent on `event_id`, so replaying a partially applied event is safe.
