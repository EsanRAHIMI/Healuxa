# @healuxa/event-contracts

> **Published Language** for all Healuxa domain events on **NATS JetStream**.
> Companion to `Healuxa_TechSpec.md` v3.3 (§9, §19) and `Healuxa_DDD_Boundaries.md` §6.
> **This package is the single source of truth for event shapes.** No service may publish or consume an event whose schema is not defined here.

This package exists to **enforce DDD boundaries** and **prevent architecture drift**:

- One event = **one producer (owner)**. Only the owner may change its schema.
- Consumers conform to the published schema; they may not assume undocumented fields.
- All cross-context state propagation happens through these events (event-built read-models), never by reaching into another service's database.

---

## Layout

```
event-contracts/
├── schemas/
│   ├── envelope.schema.json         # shared envelope wrapping every event
│   ├── common.schema.json           # shared reusable types (Money, TenantId, …)
│   ├── journey.schema.json          # Transformation-owned events
│   ├── appointment.schema.json      # Appointment-owned events
│   ├── payment.schema.json          # Payment-owned events
│   ├── subscription.schema.json     # Subscription-owned events
│   ├── provider.schema.json         # Provider Success-owned events
│   ├── commercial.schema.json       # Commercial Intelligence-owned events
│   ├── review.schema.json           # Review-owned events
│   ├── assessment.schema.json       # Assessment-owned events
│   ├── profile.schema.json          # Profile-owned events
│   ├── identity.schema.json         # Identity-owned events
│   ├── medication.schema.json       # Medication-owned events
│   ├── marketing.schema.json        # Marketing-owned events
│   └── ml.schema.json               # ML-owned events
├── src/
│   └── registry.ts                  # machine-readable event → owner/consumers/version map
├── generated/
│   ├── events.ts                    # curated, import-stable types + typed EventPayloadMap
│   ├── payloads.generated.ts        # auto-generated payload interfaces (drift check; do not edit)
│   └── healuxa_event_contracts/     # generated Pydantic models (do not edit)
├── scripts/
│   ├── generate-types.mjs           # JSON Schema → TypeScript
│   ├── generate_python.py           # JSON Schema → Pydantic v2
│   └── validate.mjs                 # validate every schema + registry consistency
└── tests/
```

---

## 1. Event naming conventions

Subjects are **lowercase, dot-delimited**: `<context>.<event>` in **past tense**.

```
<context>.<event_name>
   │            │
   │            └── what happened, past tense, snake_case  (e.g. milestone_completed)
   └── owning bounded context (singular)                   (e.g. journey, appointment)
```

Rules:

- **Context prefix is the owner.** `journey.*` is owned by Transformation; `provider.*` by Provider Success; `commercial.*` by Commercial Intelligence; etc. (full map in `src/registry.ts`).
- **Past tense, snake_case** event names (`payment.succeeded`, `appointment.no_show`).
- A NATS subject for a versioned stream is `healuxa.<context>.<event>.v<major>` (e.g. `healuxa.journey.milestone_completed.v1`). The `schema_ref` in the envelope is the authoritative version.
- No verbs implying intent of another context (no `commercial.charge_customer`); commands are sync API calls, not events.

### Stream → subject mapping

| JetStream stream | Subjects | Retention |
|---|---|---|
| `JOURNEY` | `healuxa.journey.>` | limits / replay 30d |
| `APPOINTMENT` | `healuxa.appointment.>` | limits / replay 30d |
| `BILLING` | `healuxa.payment.>`, `healuxa.subscription.>` | limits / replay 90d |
| `PROVIDER` | `healuxa.provider.>` | limits / replay 30d |
| `COMMERCIAL` | `healuxa.commercial.>` | limits / replay 90d |
| `QUALITY` | `healuxa.review.>` | limits / replay 30d |
| `CLINICAL` | `healuxa.assessment.>`, `healuxa.treatment.>`, `healuxa.medication.>` | limits / replay 30d |
| `IDENTITY` | `healuxa.auth.>` | limits / replay 14d |
| `GROWTH` | `healuxa.profile.>`, `healuxa.marketing.>` | limits / replay 30d |
| `PLATFORM` | `healuxa.ml.>` | limits / replay 14d |

---

## 2. Versioning strategy (semver-per-event)

Each event type is versioned **independently** by **major** version embedded in the subject and `schema_ref`.

- **Additive change (non-breaking)** — add an **optional** field, add a new event type, widen an enum's *output*. → **No version bump.** Bump package minor.
- **Breaking change** — remove/rename a field, make an optional field required, narrow a type, change semantics. → **New major** (`...v2`), published **alongside** `...v1` during a **dual-publish window** (≥ 1 release / 30 days). Producers emit both; consumers migrate; then `v1` is retired via ADR.
- **`version` in the envelope** is the integer major (`1`, `2`). `schema_ref` points to the exact schema `$id`.
- **Consumers must ignore unknown fields** (forward-compatible) and must **not** require fields outside the schema's `required` list.

CI gate: a PR that changes a schema in a breaking way **without** a new major version fails the `validate` check and the contract-diff check.

---

## 3. Envelope (every event)

Every message published to JetStream is an **Envelope** (`schemas/envelope.schema.json`) wrapping a typed `payload`:

```jsonc
{
  "event_id": "01J9Z…",          // ULID/UUID, unique — consumers dedupe on this (idempotency)
  "type": "journey.milestone_completed",
  "version": 1,                   // major version
  "schema_ref": "https://contracts.healuxa.com/events/journey/milestone_completed/v1",
  "occurred_at": "2026-05-30T16:00:00Z",
  "tenant_id": "healuxa-dubai",
  "producer": "transformation-engine",
  "trace_id": "…",               // OpenTelemetry trace correlation
  "correlation_id": "…",         // optional: ties a chain of events together
  "causation_id": "…",           // optional: event_id that caused this one
  "actor": { "type": "user|service|system", "id": "…" },
  "payload": { /* typed per event schema */ }
}
```

**Idempotency:** consumers MUST be idempotent keyed on `event_id`. Streams are durable with DLQ + replay.

---

## 4. Producer / consumer ownership

The authoritative, machine-readable map lives in [`src/registry.ts`](./src/registry.ts) and is validated against the schema files by `scripts/validate.mjs`. Summary (see `Healuxa_DDD_Boundaries.md` §6):

| Owner (producer) | Events |
|---|---|
| transformation-engine | `journey.created`, `journey.roadmap_updated`, `journey.milestone_completed`, `journey.phase_completed`, `journey.next_action`, `journey.at_risk`, `journey.reassessment_due`, `journey.completed` |
| appointment-service | `appointment.requested`, `appointment.created`, `appointment.accepted`, `appointment.declined`, `appointment.completed`, `appointment.no_show` |
| payment-service | `payment.succeeded`, `payment.failed`, `commission.computed` |
| subscription-service | `subscription.created`, `subscription.renewed`, `subscription.upgraded`, `subscription.downgraded`, `subscription.churned` |
| provider-success-engine | `provider.score_updated`, `provider.capacity_updated`, `provider.at_risk`, `provider.lifecycle_changed`, `provider.incentive_awarded` |
| commercial-intelligence-engine | `commercial.offer_recommended`, `commercial.upsell_opportunity`, `commercial.segment_updated`, `commercial.price_suggestion`, `commercial.forecast_updated`, `commercial.kpi_alert` |
| review-service | `review.created`, `review.moderated` |
| assessment-service | `assessment.completed` |
| profile-service | `profile.updated` |
| identity-service | `auth.user_registered`, `auth.session_revoked`, `auth.security_event` |
| medication-service | `medication.intake_missed`, `medication.refill_due` |
| marketing-service | `marketing.campaign_sent`, `marketing.engagement` |
| ml-service | `ml.model_promoted`, `ml.prediction_ready` |

> A service that is **not** the registered owner may **not** publish an event. Enforced at review time against `registry.ts` and (optionally) at runtime by the `py-common` publisher, which stamps `producer` and rejects mismatches.

---

## 5. Codegen

```bash
npm install
npm run generate          # → generated/events.ts (TS) + generated/healuxa_event_contracts/*.py (Pydantic)
npm run validate          # validate all schemas + registry consistency
```

- **TypeScript** (web/admin/NestJS): import from `@healuxa/event-contracts` — `events.ts` exposes every payload interface plus `EventPayloadMap`, `TypedEnvelope<K>`, and `EventEnvelope<T>`. `npm run generate:ts` (re)builds `payloads.generated.ts` from the schemas; CI diffs it against `events.ts` to catch drift.
- **Python** (FastAPI services): `from healuxa_event_contracts import JourneyMilestoneCompleted` (run `npm run generate:py`).

`npm run validate` checks that all 15 schemas compile, the registry has no duplicate types, and every registry `schema` ref resolves to a real `$def`. Generated files are committed so consumers don't need a build step.
