# concierge-service (port 8021)

Concierge case management (Stage E). A customer submits a **non-clinical** concierge request
(medical travel, specialist search, second-opinion coordination, logistics, other); coordinators
triage, claim and work it, propose provider options (provider-service ids only), and arrange it;
supervisors resolve escalations. Contract: `packages/api-contracts/openapi/concierge.openapi.yaml`.
Events: `concierge.case_submitted`, `concierge.case_status_changed`, `concierge.message_posted`
(`packages/event-contracts/schemas/concierge.schema.json`) — ids and metadata only.

```bash
scripts/dev/start-infra.sh                     # native Postgres/Redis/NATS/MongoDB (no Docker)
cd services/concierge-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/concierge
alembic upgrade head
uvicorn concierge_service.main:app --port 8021
```

Tests use `concierge_test`: `DATABASE_URL=...concierge_test pytest -q` (set `NATS_URL` to also run
the JetStream relay test).

## Lifecycle

```
submitted → triaged → assigned → in_progress ⇄ awaiting_customer → arranged → completed
any open state → cancelled | escalated          escalated → (supervisor) back to work | cancelled
arranged → in_progress (plan fell through)
```

`assigned` is only entered via `POST /cases/{id}/assignment`, `escalated` only via
`POST /cases/{id}/escalation`. `arranged` requires a customer-selected option. Illegal moves → 409.
Every transition, assignment and option decision is in the audit trail (`GET /cases/{id}/audit`).

## Roles (identity RBAC + ABAC here)

| Role | Permission | May |
|---|---|---|
| customer | `concierge:request` | submit, list/see own cases, cancel/escalate own, select an option, message the assigned coordinator |
| coordinator | `concierge:coordinate` | tenant work queue, triage, claim, notes, and — as assignee — progress, propose options, message |
| supervisor | `concierge:supervise` | everything a coordinator may on any tenant case, assign to others, resolve escalations |

Everyone else (other customers, other tenants, no permission) gets 404. Forged `X-Healuxa-*`
headers without the edge secret are ignored (401). Secure messages are visible only to the case's
customer and its assigned coordinator — not to other coordinators or supervisors.

## SLA

`first_response_due_at = created_at + FIRST_RESPONSE_SLA_MINUTES` (default 240). The first triage,
claim or coordinator message sets `first_responded_at`; `sla_breached` is computed on read and the
queue can filter on it.

## Data minimisation

No diagnosis or clinical fields exist. `needs_note` is optional and labelled non-clinical in the
contract; message bodies, notes and reasons are stored here only and never published in events (the
publisher rejects free-text keys).
