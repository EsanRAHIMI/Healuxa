# assessment-service

Healuxa **Assessment** bounded context (Open Host Service). Owns the `assessments` MongoDB collection only. HTTP contract: `packages/api-contracts/openapi/assessment.openapi.yaml`.

## Scaffold scope

The scaffold stores submitted assessment **responses** only. It does **not** generate recommendations, scores, diagnosis, or roadmap inputs yet. After submit, `recommended_goals` is always `[]` and `scores` is always `{}` until a later approved AI/rule-engine phase.

## Idempotency

`POST /v1/assessments` and `POST /v1/assessments/{id}/submit` declare optional `Idempotency-Key` in `assessment.openapi.yaml`. This service implements replay-safe idempotency for those endpoints (same key + same body → cached response; same key + different body → `409 idempotency_conflict`).

## Events

Emits `assessment.completed` only (see `packages/event-contracts`). No NATS consumers in this scaffold. Does not call transformation-engine on complete.

## Local run (port 8003)

```bash
source .venv/bin/activate
cd services/assessment-service
cp .env.example .env   # set MONGODB_URI, MONGODB_DATABASE
uvicorn assessment_service.main:app --host 0.0.0.0 --port 8003 --reload
```

Identity must include `assessments:create`, `assessments:read`, `assessments:write` on the default `user` role (`alembic upgrade head`, migration `0005_assessment_permissions`).

## Tests (Atlas test database)

```bash
export MONGODB_URI='mongodb+srv://...'
export MONGODB_DATABASE=healuxa_assessment_test
pytest -q
```

`MONGODB_DATABASE` must contain `test`. Destructive cleanup runs only for test database names. Without `MONGODB_URI`, Mongo tests are skipped.
