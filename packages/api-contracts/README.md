# @healuxa/api-contracts

> **Open Host Services (OHS)** — OpenAPI 3.1 contracts for every internal Healuxa service API.
> Companion to `Healuxa_TechSpec.md` v3.3 (§9) and `Healuxa_DDD_Boundaries.md` §7.
> **This package is the single source of truth for synchronous service APIs.** A consumer must use a generated client from these specs — never an ad-hoc HTTP call.

These contracts **enforce DDD boundaries** and **prevent coupling/drift**:

- A service exposes **only** its own aggregate's operations (no cross-context writes).
- Every spec reuses the **shared components** (`openapi/_shared/components.yaml`) for errors, pagination, auth, and headers — conventions are uniform and cannot drift per service.
- Breaking changes require a new path version (`/v2`) + deprecation window.

---

## Layout

```
api-contracts/
├── openapi/
│   ├── _shared/
│   │   └── components.yaml         # Error, Pagination, parameters, headers, securitySchemes
│   ├── identity.openapi.yaml
│   ├── transformation.openapi.yaml
│   ├── provider.openapi.yaml
│   ├── provider-success.openapi.yaml
│   ├── matching.openapi.yaml
│   ├── appointment.openapi.yaml
│   ├── review.openapi.yaml
│   ├── subscription.openapi.yaml
│   ├── payment.openapi.yaml
│   ├── commercial.openapi.yaml
│   ├── profile.openapi.yaml
│   ├── assessment.openapi.yaml
│   ├── treatment.openapi.yaml
│   ├── marketplace.openapi.yaml
│   ├── medication.openapi.yaml
│   ├── crm.openapi.yaml
│   ├── marketing.openapi.yaml
│   ├── notification.openapi.yaml
│   ├── media.openapi.yaml
│   ├── ai.openapi.yaml
│   └── ml.openapi.yaml
├── scripts/
│   ├── bundle.mjs                  # dereference each spec → dist/
│   └── generate-clients.mjs        # OpenAPI → TS types (openapi-typescript)
└── redocly.yaml                    # shared lint ruleset
```

Each spec is **standalone-resolvable**: it `$ref`s `_shared/components.yaml` with relative paths so `redocly lint`, bundling, and codegen all work per file.

---

## 1. Versioning

- Path-versioned: all routes live under `/v1`. Public edge route is `api.healuxa.com/v1/<domain>/*` (Traefik, TechSpec §9.4).
- **Additive** (new optional field, new endpoint) → no version bump; bump package minor.
- **Breaking** (remove/rename field, change required, change semantics) → new `/v2` path, served alongside `/v1` for ≥ 1 release / 30 days, then `/v1` retired via ADR.
- `info.version` of each spec mirrors the package version (`3.3.0`).

---

## 2. Authentication & authorization

All internal endpoints sit behind **Traefik ForwardAuth → identity-service** (TechSpec §8.3). The edge injects identity headers; services enforce RBAC/ABAC via `py-common` middleware.

- **Security scheme `bearerAuth`** (HTTP bearer, RS256 JWT) — validated **offline** via JWKS at the edge. Declared on every operation unless explicitly `security: []` (e.g. Identity login, JWKS, health).
- **Security scheme `serviceAuth`** — OAuth2 client-credentials service JWT for service-to-service calls (TechSpec §9.1). Internal-only operations require this.
- Injected request headers (documented in `_shared/components.yaml#/components/parameters`): `X-Healuxa-User`, `X-Healuxa-Roles`, `X-Healuxa-Perms`, `X-Healuxa-Tenant`, `X-Healuxa-Session`. Services trust these **only** from the edge/mesh, never from the public internet.
- Required permission per operation is documented with the `x-required-permission` extension (e.g. `appointments:create`).

`401` = missing/invalid token; `403` = authenticated but lacks permission/scope/ownership.

---

## 3. Error response standard

**Every** non-2xx response uses the shared `Error` schema (RFC 9457 problem-details-compatible):

```jsonc
{
  "type": "https://errors.healuxa.com/validation_error",
  "title": "Validation failed",
  "status": 422,
  "code": "validation_error",          // stable machine code
  "detail": "field 'scheduled_at' must be in the future",
  "instance": "/v1/appointments",
  "trace_id": "…",                      // always present for correlation
  "errors": [                            // optional field-level details
    { "field": "scheduled_at", "code": "in_past", "message": "must be in the future" }
  ]
}
```

Standard `code` values: `validation_error` (422), `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `idempotency_conflict` (409), `rate_limited` (429), `unprocessable` (422), `internal_error` (500), `service_unavailable` (503). Reusable responses live in `_shared/components.yaml#/components/responses`.

---

## 4. Pagination & filtering

**Cursor pagination** is the default (stable under high write volume → 1M+ scale):

- Request: `?limit=<1..100, default 20>&cursor=<opaque>`.
- Response: `{ "data": [...], "page": { "next_cursor": "…|null", "limit": 20, "has_more": true } }` via shared `CursorPage` wrapper.
- **Filtering:** explicit query params only (e.g. `?status=active&from=…&to=…`). No arbitrary query DSL across boundaries.
- **Sorting:** `?sort=field` / `?sort=-field` (prefix `-` = desc), restricted to a documented allow-list per endpoint.
- **Sparse fields / expansion** are opt-in per endpoint and explicitly documented; never implicit cross-service joins.

---

## 5. Idempotency

- **All non-GET mutating endpoints** accept an `Idempotency-Key` header (shared parameter `IdempotencyKey`). The service stores `(key, request-hash) → response` for ≥ 24h.
  - Same key + same body → original response replayed.
  - Same key + different body → `409 idempotency_conflict`.
- **Writes that fan out events** must be idempotent end-to-end; the emitted event's `event_id` is derived deterministically so retries don't double-publish.
- `POST` that creates a resource returns `201` + `Location`; safe to retry with the same `Idempotency-Key`.
- Concurrency control on updates via `If-Match` / `ETag` (optimistic locking) where documented.

---

## 6. Tooling

```bash
npm install
npm run lint          # redocly lint — enforces the shared ruleset (errors, security, naming)
npm run bundle        # → dist/<service>.bundled.yaml (deref'd, for publishing/mock)
npm run generate:ts   # → generated/<service>.d.ts (openapi-typescript)
```

CI runs `lint` on every PR. A spec that drops the shared error/pagination/auth components, or introduces a cross-context write, fails review.
