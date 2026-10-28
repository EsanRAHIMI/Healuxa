# provider-service (port 8005)

Provider & Catalog context (DDD §3.6): providers and their credential verification, facilities and
branches, facility staff roles, provider–facility affiliations, service offerings with a transparent
professional + facility fee breakdown, branch opening hours, and provider availability rules/exceptions.
Contract: `packages/api-contracts/openapi/provider.openapi.yaml` (v3.4). Events: `catalog.*`.

```bash
scripts/dev/start-infra.sh                     # native Postgres/Redis/NATS/MongoDB (no Docker)
cd services/provider-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/provider
alembic upgrade head
uvicorn provider_service.main:app --port 8005
```

Tests use `provider_test`: `DATABASE_URL=...provider_test pytest -q`.

Trust rules enforced here: only verified + active providers/facilities are public; activation needs a
verified, unexpired professional license; affiliations need both sides verified and the counterparty's
approval; offerings and availability need an active affiliation; availability must sit inside branch
opening hours and never overlap across branches.
