# Healuxa — Domain-Driven Design Boundaries

### Bounded Contexts · Service / Data / Event Ownership · Integration Contracts

> **Version:** 3.3 · Companion to `Healuxa_TechSpec.md` v3.3
> **Purpose:** Freeze clear service boundaries to prevent coupling, shared-database drift, and ownership ambiguity as the platform scales to 1M+ users.
> **Golden rule:** *One bounded context = one service = one database = one owner.* Every piece of data and every domain event has **exactly one authoritative owner**. Everything else is a **consumer** through a contract.

---

## Table of Contents

1. [Strategic Design — Domains & Subdomains](#1-strategic-design--domains--subdomains)
2. [Context Map (Bounded Contexts & Relationships)](#2-context-map-bounded-contexts--relationships)
3. [Bounded Context Catalog](#3-bounded-context-catalog)
4. [Service Ownership](#4-service-ownership)
5. [Data Ownership](#5-data-ownership)
6. [Event Ownership](#6-event-ownership)
7. [Integration Contracts](#7-integration-contracts)
8. [Anti-Coupling & Anti-Drift Governance](#8-anti-coupling--anti-drift-governance)

---

## 1. Strategic Design — Domains & Subdomains

Healuxa is decomposed into one **Core Domain** and supporting/generic subdomains. Investment, in-house ownership, and modeling rigor follow this classification.

| Type | Subdomain | Bounded Context(s) | Why |
|---|---|---|---|
| **Core** | **Customer Transformation** | Transformation Engine | The reason the business exists — managed outcome journeys. Maximum in-house investment. |
| **Core** | **Provider Success** | Provider Success Engine | Differentiator — optimizes supply quality/economics. |
| **Core** | **Commercial Intelligence** | Commercial Intelligence Engine | Differentiator — optimizes monetization & growth. |
| **Core** | **Matching & Ranking** | Matching Engine (+ ML) | Proprietary logic connecting demand ↔ supply on outcomes. |
| Supporting | Clinical Treatment | Treatment | Domain-specific but supports the journey. |
| Supporting | Assessment | Assessment | Feeds journey roadmaps. |
| Supporting | Provider & Catalog | Provider | Supply registry, typed providers, brands. |
| Supporting | Scheduling | Appointment | Coordination of milestones. |
| Supporting | Reviews & Quality | Review | Voice-of-customer signal. |
| Supporting | Subscription & Billing | Subscription, Payment | Monetization mechanics. |
| Supporting | Marketplace | Marketplace | Products, brands, fulfillment. |
| Supporting | Medication Adherence | Medication | Adherence + refills. |
| Supporting | CRM & Marketing | CRM, Marketing | Lead → relationship lifecycle. |
| **Generic** | Identity & Access | Identity Service | Solved problem (custom-built per requirement) — built once, reused everywhere. |
| **Generic** | Notifications | Notification | Multi-channel fan-out. |
| **Generic** | Media | Media | Upload / signed URLs / CDN. |
| **Generic** | AI Execution | AI Orchestrator | LLM execution brain (behind adapters). |
| **Generic** | ML Platform | ML Service | Model training/serving for all contexts. |
| **Generic** | Communication (WhatsApp) | WhatsApp | Channel transport. |
| **Generic** | Real-Time | Realtime Gateway | WebSocket transport. |
| **Generic** | Observability | Monitoring | System/operational health. |

---

## 2. Context Map (Bounded Contexts & Relationships)

Relationship patterns use standard DDD vocabulary:
**U** = Upstream, **D** = Downstream, **OHS** = Open Host Service (published REST/event API), **PL** = Published Language (versioned OpenAPI + JSON-Schema event contracts), **ACL** = Anti-Corruption Layer, **CF** = Conformist, **C/S** = Customer/Supplier, **P** = Partnership, **SK** = Shared Kernel.

```
                         ┌──────────────────────────────────────────────┐
                         │   IDENTITY (Generic, OHS+PL)  — upstream to ALL │
                         │   issues JWT/JWKS · introspection · RBAC/ABAC   │
                         └───────────────────────┬──────────────────────┘
                                                 │ CF (everyone conforms)
        ┌────────────────────────────────────────┼────────────────────────────────────────┐
        ▼                                         ▼                                         ▼
┌───────────────────┐   P (partnership)   ┌────────────────────┐   P    ┌──────────────────────────┐
│ TRANSFORMATION    │◀───────────────────▶│ PROVIDER SUCCESS    │◀──────▶│ COMMERCIAL INTELLIGENCE   │
│ (Core orchestrator)│                     │ (Core)              │        │ (Core)                    │
└───────┬───────────┘                     └─────────┬──────────┘        └────────────┬─────────────┘
        │ C/S (it is customer of specialized engines, consuming OHS)                  │
        │                                            │ U (provides match-signals)     │ U (offers/pricing)
        ▼ (composes via OHS APIs + subscribes to events)                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SPECIALIZED ENGINES (each OHS + PL, own DB):                                                        │
│ Assessment · Treatment · Provider · Matching(ACL→ML, D of Provider Success) · Appointment ·         │
│ Review · Subscription · Payment(ACL→gateways) · Marketplace(ACL→search) · Medication · CRM ·        │
│ Marketing · Notification(ACL→SendGrid/Twilio) · Media(ACL→S3/CloudFront) ·                          │
│ AI Orchestrator(ACL→OpenAI/Anthropic) · ML(D, consumes events) · WhatsApp(ACL→Meta)                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
        │ all domain events (PL, versioned)                              ▲ (read-only projections)
        ▼                                                                │
┌──────────────────────────┐                                  ┌──────────────────────────┐
│ NATS JetStream (event bus)│─────────────────────────────────▶│ MONITORING (D, consumes  │
│ Published Language        │                                  │ all events, read-only)   │
└──────────────────────────┘                                  └──────────────────────────┘
```

**Key relationship decisions:**

- **Identity → all = Conformist + OHS/PL.** Every service conforms to Identity's token & permission model. No service re-implements auth.
- **The three core engines = Partnership.** Transformation, Provider Success, and Commercial Intelligence evolve together; they coordinate via events + internal APIs and must change schemas in lockstep through the shared `event-contracts` package.
- **Core engines → specialized engines = Customer/Supplier.** The engines are *customers* that consume specialized engines' Open Host Services; specialized engines must not depend back on orchestrators' internal models.
- **Matching = Downstream/Conformist of Provider Success** for success-score/capacity signals (via `GET /match-signals`), and ACL toward ML.
- **All external systems sit behind an ACL** owned by exactly one service (see §7.3). No raw third-party model leaks across a boundary.
- **Monitoring & ML = pure Downstream consumers** — they build read-only projections from the event stream and never write back into other contexts' stores.

---

## 3. Bounded Context Catalog

Each context lists its **purpose**, **aggregates/entities** (with the aggregate root in bold), and **ubiquitous language** (terms that mean exactly this inside the context and must not leak with different meaning).

### 3.1 Transformation (Core orchestrator) — `transformation-engine`
- **Purpose:** Own the customer transformation journey end-to-end; orchestrate specialized engines toward outcomes/LTV.
- **Aggregates:** **Journey** (root) → Goal, Milestone, Phase, NextAction, OutcomeRecord, ReassessmentTrigger.
- **Ubiquitous language:** *Journey, Roadmap, Milestone, Phase, Outcome, Next-Best-Action, Health Index, At-Risk, Reassessment.*
- **Explicitly NOT owned:** clinical plan detail (Treatment), provider data (Provider), money (Payment/Subscription), pricing/offer authoring (Commercial).

### 3.2 Identity & Access (Generic, built in-house) — `identity-service`
- **Purpose:** Authentication, authorization, sessions, tokens, RBAC/ABAC, audit, API keys, S2S auth.
- **Aggregates:** **User** (root) → Credential, MfaFactor, Consent; **Session** → Device; **Role** → Permission; **ApiKey**; **ServiceClient**; **JwksKey**.
- **Ubiquitous language:** *Principal, Role, Permission, Scope, Tenant, Session, Device, Introspection, JWKS, Service Client.*
- **Note:** "User" here is the *security principal* only — profile/medical attributes live in Profile context.

### 3.3 Profile — `profile-service`
- **Purpose:** Customer / medical / beauty / body profiles (flexible documents).
- **Aggregates:** **CustomerProfile** (root), MedicalProfile, BeautyProfile, BodyProfile.
- **Language:** *Profile, Lifecycle Stage, VIP Tier, Consent, Score snapshot.*

### 3.4 Assessment — `assessment-service`
- **Purpose:** Structured assessments that seed roadmaps.
- **Aggregates:** **Assessment** (root) → Question, Response, Result.
- **Language:** *Assessment, Result, Recommendation.*

### 3.5 Treatment — `treatment-service`
- **Purpose:** Clinical treatment plans, steps, approvals.
- **Aggregates:** **TreatmentPlan** (root) → TreatmentStep, Approval.
- **Language:** *Treatment Plan, Step, Clinical Approval.* (Feeds journey milestones; does not own the journey.)

### 3.6 Provider & Catalog — `provider-service`
- **Purpose:** Typed providers, clinics, brands, service catalog, availability, geo.
- **Aggregates:** **Provider** (root) → ServiceOffering, Availability; **Clinic**; **Brand**.
- **Language:** *Provider, Specialty, Service, Availability, Commission Rate, Quality Score (cached), Success Score (cached).*
- **Note:** `quality_score` / `success_score` columns are **read-model caches** owned authoritatively by Review and Provider Success respectively (updated via events).

### 3.7 Matching & Ranking (Core) — `matching-service`
- **Purpose:** Rank and select providers for a milestone need.
- **Aggregates:** **MatchRequest** (root) → Candidate, Ranking, Explanation.
- **Language:** *Match, Candidate, Rank, Weight, Explanation, Capacity-aware.*

### 3.8 Scheduling — `appointment-service`
- **Purpose:** Slots, bookings, lifecycle, no-shows.
- **Aggregates:** **Appointment** (root) → Slot, StatusTransition.
- **Language:** *Appointment, Slot, Booking, No-show, Reschedule.*

### 3.9 Review & Quality — `review-service`
- **Purpose:** Customer ratings + Bayesian Quality Score.
- **Aggregates:** **Review** (root); **ProviderQuality** (root, score projection).
- **Language:** *Review, Rating, Dimension, Moderation, Quality Score.* (Authoritative owner of `quality_score`.)

### 3.10 Provider Success (Core) — `provider-success-engine`
- **Purpose:** Provider health, performance, capacity, lifecycle, incentives.
- **Aggregates:** **ProviderPerformance** (root) → CapacityState, AcceptanceMetric, ResponseMetric, SatisfactionMetric, RevenueMetric; **ProviderLifecycle**; **IncentiveProgram** → IncentiveAward.
- **Language:** *Success Score, Tier, Capacity Health, Acceptance Rate, Response Time, Lifecycle Stage, Incentive.* (Authoritative owner of `success_score`.)

### 3.11 Commercial Intelligence (Core) — `commercial-intelligence-engine`
- **Purpose:** Revenue/pricing/offer/packaging/LTV/segmentation/forecast optimization.
- **Aggregates:** **Offer** (root) → OfferAssignment; **Package**; **PricingRule**; **Segment** → SegmentMember; **Experiment**; **Promotion**; **Forecast**; **KpiSnapshot**.
- **Language:** *Offer, Package, Segment, Cohort, LTV, Elasticity, Uplift, Forecast, KPI, Opportunity.*
- **Note:** Owns commercial *decisions*. It does **not** own the money ledger (Payment) or plan definitions (Subscription) — it reads those via events/APIs.

### 3.12 Subscription — `subscription-service`
- **Purpose:** Plans, credits, wallet, renewals, upgrades.
- **Aggregates:** **Subscription** (root) → Plan, Credit, WalletEntry, RenewalSchedule.
- **Language:** *Plan, Credit, Renewal, Upgrade/Downgrade, Wallet.*

### 3.13 Payment — `payment-service`
- **Purpose:** Payments, invoices, commissions, dunning (money ledger = source of truth).
- **Aggregates:** **Payment** (root); **Invoice**; **Commission**; **DunningProcess**.
- **Language:** *Payment, Invoice, Commission, Dunning, Settlement.*

### 3.14 Marketplace — `marketplace-service`
- **Purpose:** Products, brands, orders, fulfillment.
- **Aggregates:** **Product** (root); **Order** → OrderLine, Fulfillment.
- **Language:** *Product, Brand, Order, Fulfillment, Stock.*

### 3.15 Medication — `medication-service`
- **Purpose:** Prescriptions, adherence schedule/score, refills.
- **Aggregates:** **Prescription** (root) → MedicationScheduleEntry, IntakeConfirmation; **Refill**.
- **Language:** *Prescription, Intake, Adherence Score, Refill.*

### 3.16 CRM — `crm-service`
- **Purpose:** Leads, pipeline, tasks, relationships.
- **Aggregates:** **Lead** (root); **Pipeline** → Stage; **CrmTask**.
- **Language:** *Lead, Pipeline, Stage, Task.*

### 3.17 Marketing — `marketing-service`
- **Purpose:** Campaigns, content, automation flows.
- **Aggregates:** **Campaign** (root) → Audience, Content, FlowStep.
- **Language:** *Campaign, Audience, Flow, Content.*

### 3.18–3.23 Generic transport/platform contexts
- **Notification** (`notification-service`): **NotificationRequest** → Delivery, Preference, ChannelPolicy. ACL → SendGrid/Twilio.
- **Media** (`media-service`): **MediaAsset** → SignedUrl. ACL → S3/CloudFront/KMS.
- **AI Orchestrator** (`ai-orchestrator`): **AiSession** → Turn, MemoryRef, Guardrail. ACL → OpenAI/Anthropic.
- **ML** (`ml-service`): **Model** → FeatureSet, TrainingRun, Prediction. Downstream consumer.
- **WhatsApp** (`whatsapp-service`): **WaConversation** → Message, FlowState, Template. ACL → Meta Cloud API.
- **Real-Time** (`realtime-gateway`): **Topic** → Subscription, Connection (ephemeral). No business state.
- **Monitoring** (`monitoring-service`): read-only projections, LiveOps views. Downstream consumer of all events.

---

## 4. Service Ownership

Each service is owned by exactly one team and is independently deployable. "Owns" means: sole authority to change schema, business logic, and emitted contracts.

| Service | Owning team (suggested) | Core/Supporting/Generic | May write to |
|---|---|---|---|
| transformation-engine | Journey / Core | Core | own DB only |
| provider-success-engine | Supply / Core | Core | own DB + ClickHouse projection |
| commercial-intelligence-engine | Growth / Core | Core | own DB + ClickHouse projection |
| matching-service | Core / Matching | Core | own DB |
| identity-service | Platform Security | Generic | own DB only |
| profile-service | Customer Data | Supporting | own DB |
| assessment-service | Clinical Product | Supporting | own DB |
| treatment-service | Clinical Product | Supporting | own DB |
| provider-service | Supply | Supporting | own DB |
| appointment-service | Coordination | Supporting | own DB |
| review-service | Supply Quality | Supporting | own DB |
| subscription-service | Monetization | Supporting | own DB |
| payment-service | Monetization | Supporting | own DB (money ledger) |
| marketplace-service | Commerce | Supporting | own DB |
| medication-service | Clinical Product | Supporting | own DB |
| crm-service | Growth | Supporting | own DB |
| marketing-service | Growth | Supporting | own DB |
| notification-service | Platform | Generic | own DB |
| media-service | Platform | Generic | own DB + S3 |
| ai-orchestrator | AI | Generic | own DB + vector |
| ml-service | AI/ML | Generic | own DB + registry |
| whatsapp-service | Channels | Generic | own DB |
| realtime-gateway | Platform | Generic | none (ephemeral) |
| monitoring-service | Platform SRE | Generic | own ClickHouse only |

**Rule:** No service has DB credentials for another service's database. The only cross-service access paths are **OHS APIs** and **the event bus**.

---

## 5. Data Ownership

**Principle (TechSpec §7.2):** Each service owns its tables/collections. No direct cross-service DB reads. Cross-context data is obtained via **API (sync)** or **event-built local read-models (async)**.

### 5.1 Authoritative owners of shared/contested fields

These are the fields most likely to cause drift. Each has exactly one writer; everyone else holds a **read-model cache** updated only via events.

| Field / concept | Authoritative owner | Replicated to (read-only cache) | Sync mechanism |
|---|---|---|---|
| Security principal (`user_id`, roles, perms) | **Identity** | every service (claims in JWT) | JWT claims + introspection |
| Profile attributes, VIP tier, scores doc | **Profile** | Transformation, Commercial (snapshots) | `profile.updated` event |
| `quality_score` | **Review** | Provider (cache col), Matching, Provider Success | `review.created` → recompute |
| `success_score`, `tier`, `capacity` | **Provider Success** | Provider (cache col), Matching | `provider.score_updated`, `provider.capacity_updated` |
| Money ledger (payments, invoices, commissions) | **Payment** | Commercial (revenue projection), Provider Success (economics) | `payment.*`, `commission.computed` |
| Plan/credit/renewal state | **Subscription** | Commercial, Transformation | `subscription.*` |
| Offer / price / segment decisions | **Commercial Intelligence** | Transformation (presents), Subscription/Marketing (applies) | `commercial.*` |
| Journey/milestone/outcome state | **Transformation** | Commercial (cohorts), Provider Success (outcome attribution) | `journey.*` |
| Appointment lifecycle | **Appointment** | Transformation, Provider Success, Commercial | `appointment.*` |

### 5.2 Database isolation

- **Per-service logical DB** (TechSpec §7.3): `identity`, `payments`, `commercial`, `provider_success`, `transformation`, etc. **Identity and Payments isolated first** (physically separable).
- **Analytics engines (Provider Success, Commercial Intelligence, Monitoring)** build **their own ClickHouse projections from the event stream** — they **never** query another service's primary DB (TechSpec §7.2).
- **MongoDB collections** (Profile, Assessment, AI) are owned by their single service; CSFLE for medical/PII.

### 5.3 Forbidden patterns (drift sources)

- ❌ Shared database / shared tables between services.
- ❌ One service reading another's tables directly (even read replica).
- ❌ Foreign keys across service boundaries (use IDs as opaque references).
- ❌ "Temporary" direct DB hop "just for a report" — use events/projections.
- ❌ Writing a field whose authoritative owner is another context.

---

## 6. Event Ownership

Events are part of the **Published Language**. Each event has exactly **one producer (owner)**; the owner defines and versions its schema in `packages/event-contracts`. Consumers may not assume fields beyond the published schema.

### 6.1 Producer → event ownership

| Owning context | Owned events (authoritative) |
|---|---|
| **Transformation** | `journey.created`, `journey.roadmap_updated`, `journey.milestone_completed`, `journey.phase_completed`, `journey.next_action`, `journey.at_risk`, `journey.reassessment_due`, `journey.completed` |
| **Identity** | `auth.session_revoked`, `auth.security_event`, `auth.user_registered` |
| **Profile** | `profile.updated` |
| **Assessment** | `assessment.completed` |
| **Appointment** | `appointment.requested`, `appointment.created`, `appointment.accepted`, `appointment.declined`, `appointment.completed`, `appointment.no_show` |
| **Review** | `review.created`, `review.moderated` |
| **Payment** | `payment.succeeded`, `payment.failed`, `commission.computed` |
| **Subscription** | `subscription.created`, `subscription.renewed`, `subscription.upgraded`, `subscription.downgraded`, `subscription.churned` |
| **Provider Success** | `provider.score_updated`, `provider.capacity_updated`, `provider.at_risk`, `provider.lifecycle_changed`, `provider.incentive_awarded` |
| **Commercial Intelligence** | `commercial.offer_recommended`, `commercial.upsell_opportunity`, `commercial.segment_updated`, `commercial.price_suggestion`, `commercial.forecast_updated`, `commercial.kpi_alert` |
| **Medication** | `medication.intake_missed`, `medication.refill_due` |
| **Marketing** | `marketing.campaign_sent`, `marketing.engagement` |
| **ML** | `ml.model_promoted`, `ml.prediction_ready` |

### 6.2 Consumer subscriptions (who listens to what)

| Consumer | Subscribes to |
|---|---|
| **Transformation** | `assessment.completed`, `appointment.completed`, `review.created`, `payment.succeeded`, `payment.failed`, `subscription.*`, `commercial.upsell_opportunity`, `commercial.offer_recommended`, `medication.intake_missed` |
| **Provider Success** | `appointment.requested\|accepted\|declined\|completed\|no_show`, `review.created`, `payment.succeeded`, `commission.computed`, `journey.milestone_completed` |
| **Commercial Intelligence** | `payment.*`, `subscription.*`, `journey.*`, `appointment.completed`, `marketing.*`, `review.*`, `provider.*` |
| **Matching** | `provider.score_updated`, `provider.capacity_updated` |
| **Subscription / Marketing** | `commercial.price_suggestion`, `commercial.offer_recommended` |
| **Notification** | reminders + offers across `journey.*`, `appointment.*`, `medication.*`, `payment.failed`, `commercial.offer_recommended`, `provider.incentive_awarded` |
| **ML** | all events (training labels) |
| **Monitoring** | all events (read-only LiveOps) |

### 6.3 Event contract rules

- **Versioned** subjects/schemas (`/v1`); additive changes are non-breaking; breaking changes require a new version + dual-publish window.
- **JSON-Schema validated** at publish and consume.
- **Idempotent consumers** keyed by `event_id`; durable streams + DLQ + replay (TechSpec §9.2).
- Every event carries an **envelope**: `event_id`, `type`, `version`, `occurred_at`, `tenant_id`, `trace_id`, `producer`, `payload`.

---

## 7. Integration Contracts

Three contract types only. Anything outside these is forbidden coupling.

### 7.1 Synchronous — Open Host Service (REST/gRPC over `healuxa-net`)

Each context publishes a stable, versioned OpenAPI 3.1 contract in `packages/api-contracts`. Internal callers use generated clients, **not** ad-hoc HTTP. Resilience required: timeouts, retries, circuit breakers, idempotency keys; S2S auth via service JWT/mTLS (TechSpec §9.1).

| Provider context | Published API (consumed internally by) |
|---|---|
| Identity | `/v1/auth/introspect`, `/.well-known/jwks.json`, `/v1/iam/*` (edge + all) |
| Provider | `/v1/providers`, `/v1/services` (Matching, Transformation) |
| Provider Success | `GET /v1/provider-success/match-signals?ids=` (Matching) |
| Matching | `/v1/matching/*` (Transformation) |
| Appointment | `/v1/appointments` (Matching, Transformation) |
| Commercial | `/v1/commercial/offers/{user}`, `/upsell/{user}` (Transformation, Web) |
| Subscription | `/v1/subscriptions` (Transformation, Commercial) |
| Payment | `/v1/payments` (Subscription, Marketplace) |
| ML | internal predict/rank endpoints (Matching, Commercial, Provider Success) |

**Rule:** A synchronous call is allowed only for **read or command on the provider's own aggregate**. Never to fetch data the caller should have cached from events on a hot path.

### 7.2 Asynchronous — Published Language on NATS JetStream

The contract is the **versioned event schema** (§6.3). Producers own it; consumers conform. This is the **preferred** integration for cross-context state propagation (read-models), keeping contexts decoupled.

### 7.3 Anti-Corruption Layers (external systems)

Every external dependency is wrapped by **exactly one** owning service. External models never cross a Healuxa boundary; only internal domain types do.

| External system | ACL owner | Internal abstraction |
|---|---|---|
| OpenAI / Anthropic | ai-orchestrator | `LLMProvider` adapter (swappable) |
| Tap Payments / Stripe | payment-service | `PaymentGateway` port |
| Meta WhatsApp Cloud API | whatsapp-service | `MessagingChannel` port |
| SendGrid / Twilio | notification-service | `EmailSender` / `SmsSender` ports |
| AWS S3 / CloudFront / KMS | media-service | `ObjectStore` / `SignedUrl` ports |
| MongoDB Atlas | profile/assessment/ai | repository abstraction |
| OpenSearch / Meilisearch | marketplace-service | `SearchIndex` port |

### 7.4 Shared Kernel (deliberately minimal)

Shared only through versioned packages (no shared runtime DB): `packages/event-contracts` (event schemas), `packages/api-contracts` (OpenAPI + clients), `packages/ts-types`, `packages/py-common` (auth middleware, envelope, observability). Changes to shared kernel require sign-off from all three core-engine owners (Partnership).

---

## 8. Anti-Coupling & Anti-Drift Governance

These rules keep boundaries intact as the system evolves.

1. **One owner per datum, one producer per event.** Enforced in code review against §5–§6 tables.
2. **No shared databases; no cross-service DB credentials.** Verified in deploy config; each service gets only its own DSN.
3. **No cross-boundary foreign keys.** IDs are opaque references resolved via API/events.
4. **Contracts live in `packages/*` and are versioned.** Breaking change = new version + migration window; CI fails consumers on contract drift.
5. **External systems only behind their single ACL owner.** No second service may import a third-party SDK that another context owns.
6. **Read-models, not reach-ins.** Need another context's data on a hot path? Project it locally from events; do not synchronously reach into the owner repeatedly.
7. **Core engines compose, never absorb.** Transformation/Provider Success/Commercial orchestrate specialized engines through their OHS; they must not reimplement specialized logic or read specialized DBs.
8. **Analytics is downstream-only.** Monitoring, Commercial, Provider Success build projections from events; they never write into other contexts.
9. **Conformist to Identity.** No service issues or validates tokens itself beyond the shared `py-common` middleware + JWKS.
10. **Drift audits.** Architecture review per phase (TechSpec §26) checks: new tables map to one owner, new events to one producer, no new external SDK outside an ACL, no new cross-service DB access.

---

*Healuxa DDD Boundaries v3.3 · Companion to Healuxa_TechSpec.md · Confidential · Dubai, UAE*
