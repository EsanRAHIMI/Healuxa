# Healuxa — Full Technical Specification

### AI-Powered Luxury Transformation & Optimization Ecosystem · Dubai

> **Version:** 3.3 · Production Blueprint
> **Core model:** Outcome-centric, **triple-layer optimization** — **Customer Success** (Transformation Engine §3) + **Provider Success** (Provider Success Engine §13) + **Commercial Intelligence** (Commercial Intelligence Engine §14). Organized around transformation journeys & lifetime outcomes, not bookings or listings.
> **Architecture:** Event-driven microservices · Polyglot persistence · Dokploy-deployed
> **Scale target:** 1,000,000+ users in year one (design without mid-flight rewrites)
> **Primary stacks:** Next.js 15 (web) · Expo / React Native (mobile) · FastAPI (Python 3.12 services) · NestJS optional for high-throughput transactional services · PostgreSQL 16 · MongoDB Atlas · Redis 7 · NATS JetStream · ClickHouse · S3 + CloudFront
> **Market:** High-net-worth clients, Dubai, UAE
> **Languages:** EN · AR · FA · RU

---

## Table of Contents

1. [System Overview, Outcome-Centric Vision & Success KPIs](#1-system-overview-outcome-centric-vision--success-kpis)
2. [Architecture Principles](#2-architecture-principles)
3. [Transformation Engine — Core Orchestrator](#3-transformation-engine--core-orchestrator)
4. [Technology Stack (Latest Stable)](#4-technology-stack-latest-stable)
5. [Specialized Engines — Service Catalog & Bounded Contexts](#5-specialized-engines--service-catalog--bounded-contexts)
6. [Project Structure (Multi-Folder, Independently Deployable)](#6-project-structure-multi-folder-independently-deployable)
7. [Polyglot Data Layer Strategy](#7-polyglot-data-layer-strategy)
8. [Identity Service — Enterprise IAM (Core Platform Service)](#8-identity-service--enterprise-iam-core-platform-service)
9. [Inter-Service Communication](#9-inter-service-communication)
10. [Core Domain Services](#10-core-domain-services)
11. [Provider Matching Engine](#11-provider-matching-engine)
12. [Reviews, Ratings & Provider Quality Score](#12-reviews-ratings--provider-quality-score)
13. [Provider Success Engine](#13-provider-success-engine)
14. [Commercial Intelligence Engine](#14-commercial-intelligence-engine)
15. [Medication & Treatment Adherence](#15-medication--treatment-adherence)
16. [AI / ML Platform & Continuous Learning Loop](#16-ai--ml-platform--continuous-learning-loop)
17. [Data Models](#17-data-models)
18. [Frontend — Web, Admin & Mobile](#18-frontend--web-admin--mobile)
19. [Real-Time & Eventing](#19-real-time--eventing)
20. [Monitoring & Observability Service](#20-monitoring--observability-service)
21. [Subscriptions, Payments & Marketplace](#21-subscriptions-payments--marketplace)
22. [WhatsApp Automation & Notifications](#22-whatsapp-automation--notifications)
23. [Scalability & Performance Plan (1M+ Users)](#23-scalability--performance-plan-1m-users)
24. [Deployment on Dokploy](#24-deployment-on-dokploy)
25. [Environment Variables (Per Service)](#25-environment-variables-per-service)
26. [Implementation Roadmap](#26-implementation-roadmap)

---

## 1. System Overview, Outcome-Centric Vision & Success KPIs

Healuxa is a **luxury transformation and optimization ecosystem** that helps high-net-worth, time-poor clients in Dubai achieve their **personal beauty, wellness, longevity, and body-optimization goals** through a **fully managed transformation journey**. It is **not an MVP**, and it is **not a healthcare/beauty marketplace** — bookings, provider listings, products, and payments are *means*, never the *purpose*. The purpose is **customer outcomes and long-term transformation**.

### 1.1 Triple-Layer, Outcome-Centric Product Model

Healuxa optimizes the ecosystem through **three core optimization engines**:

- **Customer Success** — **Transformation Engine** (§3): every client has a **Transformation Journey** (goals, milestones, phases, outcome metrics). The client only **decides, approves, and pays**; Healuxa orchestrates everything else across **App + WhatsApp + Web**.
- **Provider Success** — **Provider Success Engine** (§13): continuously optimizes the **provider ecosystem** (performance, quality, capacity, satisfaction, economics, lifecycle, retention, incentives).
- **Commercial Intelligence** — **Commercial Intelligence Engine** (§14): continuously optimizes the **business** (revenue, pricing, packaging, upsell/cross-sell, LTV, cohorts, segmentation, forecasting, promotion performance, business KPIs).

The three engines work together (via the **Matching Engine §11**, the event bus, and shared ML) so the **right customer, best provider, and optimal commercial offer** converge — maximizing outcomes, ecosystem health, and sustainable revenue. The platform is **organized around journeys and outcomes**, not transactions.

### 1.2 Success KPIs (priority order)

**Customer side (primary):**

1. **Customer transformation success** — measurable progress toward defined goals.
2. **Retention** — active clients retained over 30/60/90/180/365 days.
3. **Subscription duration** — average tenure / months subscribed.
4. **Journey completion** — % of milestones and phases completed on plan.
5. **Customer satisfaction** — NPS, CSAT, satisfaction per milestone.
6. **Lifetime Value (LTV)** — projected and realized revenue per client.
7. **Recurring revenue** — MRR / ARR, net revenue retention, expansion.

**Provider side (ecosystem health):**

8. **Provider Success Score**, provider retention & lifecycle health, acceptance rate & response time, provider-driven satisfaction, provider economics.

**Commercial side (business optimization):**

9. **Revenue & margin optimization**, conversion-funnel rates, upsell/cross-sell rate, promotion ROI, pricing efficiency, forecast accuracy, growth-opportunity capture.

> Vanity metrics (raw bookings, listing counts, GMV) are **secondary diagnostics**, never primary targets. Dashboards, ML objectives, and incentives are tuned to the KPIs above.

### 1.3 Vision → Capability Coverage Matrix

| Vision element | Owning engine(s) | Status |
|---|---|---|
| **Fully managed transformation journey** | **Transformation Engine** | **Core orchestrator (§3)** |
| **Provider ecosystem optimization** | **Provider Success Engine** | New (§13) |
| **Business/revenue optimization** | **Commercial Intelligence Engine** | **New (§14)** |
| Maximize outcomes, retention, LTV; next-best-action | Transformation + Commercial Intelligence + ML + AI | New (§3, §14, §16) |
| Unified management of beauty/health/fitness/lifestyle | Profile, Treatment, Appointment, Marketplace | Core |
| Transparent personalized roadmap | Transformation + Treatment + AI | Core |
| 10 service categories | Provider/Catalog + Marketplace + Medication | Core |
| Connect to all provider types | Provider Engine (typed providers) | Expanded |
| ML-driven path design + continuous learning | ML Engine + AI Orchestrator | New (§16) |
| Curated Provider Matching & Scheduling | Matching Engine + Provider Success | New (§11, §13) |
| Continuous provider rating + quality score | Review Engine + Provider Success | New (§12, §13) |
| Concierge UX ("decide, approve, pay") | Transformation + AI + CRM + Notification | Core |
| App + WhatsApp + Web parity | Web, Mobile, WhatsApp engines | Web fully specified (§18) |
| Coordination, scheduling, reminders, follow-up | Appointment + Notification + Transformation | Core |
| Medication & treatment adherence | Medication Engine | New (§15) |
| Live operational control panel | Monitoring Service + Live Ops | New (§20) |
| Unified, fast, secure, enterprise identity | Identity Service (Enterprise IAM) | Expanded (§8) |

---

## 2. Architecture Principles

1. **Triple-layer, outcome-centric, orchestrated.** The platform optimizes **Customer Success** (§3), **Provider Success** (§13), and **Commercial Intelligence** (§14) together, organized around **transformation journeys and lifetime outcomes**, not bookings or listings. The Transformation Engine is the central business orchestrator; **all other systems are enterprise-grade specialized engines** it composes (CRM, Marketing, Matching, Scheduling, Marketplace, Payments, Subscriptions, Assessments, WhatsApp, AI, Provider Success, Commercial Intelligence). None are simplified.
2. **Core business logic stays in-platform.** Journey logic, provider-success scoring, commercial/revenue intelligence, matching, ranking, treatment planning, billing rules, adherence, identity, and orchestration are **owned by Healuxa services**. Third parties (LLMs, payment gateways, WhatsApp, KMS) are integrations behind adapters, never the source of truth.
3. **Microservices by bounded context.** Each service lives in its **own root folder**, owns its data, ships its own `Dockerfile`, exposes its own port, deploys as an **independent Dokploy application**.
4. **Event-driven.** Domain events on **NATS JetStream**. The Transformation, Provider Success, and Commercial Intelligence engines subscribe broadly to drive optimization on all three layers.
5. **Polyglot persistence.** PostgreSQL (transactional truth), MongoDB Atlas (flexible docs), Redis (cache/queue/geo/sessions), S3 + CloudFront (media), vector store (AI memory), ClickHouse/Timescale (analytics & intelligence).
6. **Stateless services, scale horizontally.** Any service runs N replicas behind Traefik.
7. **Enterprise unified identity (SSO-like).** One **Identity Service** (§8); RS256 JWT + JWKS; validated at the edge.
8. **Contracts first.** OpenAPI 3.1 + versioned event schemas (`/v1`).
9. **Observability is mandatory.** Logs (Loki), metrics (Prometheus), traces (OTel → Tempo), errors (Sentry), business events (Live Ops + Commercial Intelligence).
10. **Security & compliance by default.** Field-level encryption, TLS, RBAC + fine-grained permissions, audit + security-event tracking, consent, tenant isolation.
11. **Dubai-first latency.** `me-central-1` / `me-south-1`; S3 + CloudFront edge; Atlas near UAE.

---

## 3. Transformation Engine — Core Orchestrator

> **The heart of Healuxa (Customer Success layer).** Standalone, enterprise-grade business service (`services/transformation-engine`, PostgreSQL, internal port **8000**) that owns the **customer transformation journey** and orchestrates every specialized engine toward **customer outcomes and lifetime value**. Distinct from the **AI Orchestrator** (§16, AI/LLM execution brain it uses), **Treatment Service** (§10, clinical detail), and its peers **Provider Success Engine** (§13) and **Commercial Intelligence Engine** (§14).

### 3.1 Mission

Turn each client's goals into a **fully managed, continuously optimized transformation journey** maximizing measurable outcomes, satisfaction, retention, and LTV — with the client only deciding, approving, paying.

### 3.2 Responsibilities

- Builds personalized transformation roadmaps; defines goals & milestones.
- Coordinates treatments/services (composes Treatment, Matching, Scheduling, Marketplace, Medication).
- Manages timelines & dependencies (sequencing, blocking, critical path).
- Monitors progress; triggers reassessments.
- Optimizes retention & renewals (with CRM, Subscription, **Commercial Intelligence §14**).
- Recommends next actions (NBA); maximizes outcomes & LTV.

### 3.3 Orchestration Model

```
        CUSTOMER SUCCESS            PROVIDER SUCCESS         COMMERCIAL INTELLIGENCE
   ┌────────────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐
   │  TRANSFORMATION ENGINE  │  │ PROVIDER SUCCESS    │  │ COMMERCIAL INTELLIGENCE     │
   │  (journeys · outcomes)  │◀▶│ ENGINE (§13)        │  │ ENGINE (§14)                │
   └───────────┬─────────────┘  └─────────┬───────────┘  └───────────────┬─────────────┘
               │  (composes via sync API + async events on NATS JetStream)│
   ┌──────────┬┴─────────┬──────────┬──────────┬──────────┬──────────┬───┴──────┐
   ▼          ▼          ▼          ▼          ▼          ▼          ▼          ▼
Assessment Treatment  Matching  Scheduling Marketplace Payments  Subscription Medication
   └──────────┴───────┬──┴──────────┴──────────┴──────────┴──────────┴──────────┘
                      ▼                ▼                ▼              ▼
                AI Orchestrator     ML Engine        CRM Engine   Marketing · WhatsApp · Notification · Review
```

- **Specialized engines stay enterprise-grade.** The three optimization engines **compose and inform** them, never replace their logic.

### 3.4 Domain Model (journey aggregate)

```
Journey { id, user_id, tenant_id, primary_goals[], status, started_at,
          target_completion, health_index, ltv_projection }
Goal · Milestone · Phase · NextAction · OutcomeRecord · ReassessmentTrigger   (as in v3.2)
```

### 3.5 Journey Lifecycle

```
draft → onboarding → active → at_risk ⇄ active → renewing → completed → (churned → reactivation)
```

### 3.6 Event Choreography (examples)

```
assessment.completed → build roadmap (goals, milestones, phases)
appointment.completed → advance milestone + outcome + maybe reassess
review.created → factor satisfaction into journey health
payment.succeeded → sustain; payment.failed → at_risk + retention play
commercial.upsell_opportunity → present offer at the right moment (from §14)
journey.milestone_due → schedule via Matching + Appointment + Notification
```

Emits: `journey.created`, `journey.roadmap_updated`, `journey.milestone_completed`, `journey.phase_completed`, `journey.next_action`, `journey.at_risk`, `journey.reassessment_due`, `journey.completed`.

### 3.7 APIs — `/v1/journeys`

`POST /journeys` · `GET /journeys/{user}` · `GET /journeys/{id}/roadmap` · `POST /journeys/{id}/goals` · `GET /journeys/{id}/milestones` · `POST /journeys/{id}/milestones/{m}/complete` · `GET /journeys/{id}/next-actions` · `POST /journeys/{id}/reassess` · `GET /journeys/{id}/outcomes` · `GET /journeys/{id}/health`.

### 3.8 Data & Intelligence

PostgreSQL (journey structure) + MongoDB (roadmap narratives). Uses AI Orchestrator (roadmaps/explanations), ML Engine (NBA/churn/LTV), and Commercial Intelligence (offer timing). Objective = **Success KPIs §1.2**.

---

## 4. Technology Stack (Latest Stable)

| Layer | Technology | Notes |
|---|---|---|
| Web app | **Next.js 15** (App Router, React 19, RSC) + TypeScript 5.x | PWA, SSR/ISR, luxury UX |
| Web UI kit | TailwindCSS + shadcn/ui + Radix + Framer Motion | Shared design tokens |
| Web data | TanStack Query + Zustand | Server-state + client-state |
| Mobile | **Expo SDK 52+ / React Native (New Architecture)** + TypeScript | iOS + Android |
| Backend (services) | **Python 3.12 + FastAPI** (async, Pydantic v2, Uvicorn/Gunicorn) | Default for all domain + AI services |
| High-throughput option | **NestJS 10 (Node 22)** | chat/realtime/notification fan-out |
| API edge / routing | **Traefik v3** (native to Dokploy) | Host + path routing, TLS, ForwardAuth, rate limit |
| Relational DB | **PostgreSQL 16** (managed, secure) + PgBouncer | Primary source of truth |
| Document DB | **MongoDB Atlas** (M-tier, encrypted) | Flexible profiles/assessments/content |
| Cache / queue / geo / sessions | **Redis 7** (cluster mode) | Cache, rate-limit, geo, sessions, broker |
| Event streaming | **NATS JetStream** | Durable domain events |
| Background jobs | **Celery** / BullMQ on Redis | Reminders, billing, AI/ML, intelligence pipelines |
| Object storage | **AWS S3** (`me-south-1`) + **CloudFront** | Media, docs, before/after, lab PDFs |
| Vector memory | **pgvector** → **Qdrant** | Patient memory / semantic recall |
| Analytics & intelligence | **ClickHouse / TimescaleDB** | Live Ops, KPIs, provider + commercial analytics |
| LLM providers | OpenAI + Anthropic (behind adapter) | Swappable via AI Orchestrator |
| Search | OpenSearch / Meilisearch | Marketplace + provider search |
| Observability | **Prometheus + Grafana + Loki + Tempo + OpenTelemetry + Sentry + Uptime Kuma** | Monitoring service (§20) |
| Identity / IAM | **Custom Healuxa Identity Service** (FastAPI) | Enterprise IAM, **no external IAM** (§8) |
| Auth security libs | Argon2id, Authlib/PyJWT, pyotp, `cryptography` | Proven libraries; logic in-platform |
| Deploy | **Dokploy** (Docker + Traefik) | Per-service app, Dockerfile/Nixpacks |
| IaC / config | docker-compose (local) + Dokploy + `.env` per service | Reproducible |

---

## 5. Specialized Engines — Service Catalog & Bounded Contexts

> All systems below are **enterprise-grade specialized engines**, **not simplified**. Each row is an **independent root folder + independent Dokploy application** on the private `healuxa-net` network.

| # | Service (folder) | Role | Primary store | Internal port | Public route |
|---|---|---|---|---|---|
| 0 | `services/transformation-engine` | **Core orchestrator (Customer Success)** | PostgreSQL + Mongo | **8000** | `/v1/journeys` |
| 1 | `services/identity-service` | **Enterprise IAM** | PostgreSQL + Redis | 8001 | `/v1/auth`, `/v1/users`, `/v1/iam` |
| 2 | `services/profile-service` | Customer / medical / beauty / body profiles | MongoDB Atlas | 8002 | `/v1/profiles` |
| 3 | `services/assessment-service` | **Assessment Engine** | MongoDB Atlas | 8003 | `/v1/assessments` |
| 4 | `services/treatment-service` | Clinical treatment plans, steps, approvals | PostgreSQL + Mongo | 8004 | `/v1/treatment-plans` |
| 5 | `services/provider-service` | Typed providers, clinics, brands, catalog | PostgreSQL | 8005 | `/v1/providers`, `/v1/services` |
| 6 | `services/matching-service` | **Matching Engine** | PostgreSQL + Redis geo | 8006 | `/v1/matching` |
| 7 | `services/appointment-service` | **Scheduling Engine** | PostgreSQL | 8007 | `/v1/appointments` |
| 8 | `services/review-service` | **Review Engine** | PostgreSQL | 8008 | `/v1/reviews` |
| 9 | `services/subscription-service` | **Subscription Engine** | PostgreSQL | 8009 | `/v1/subscriptions` |
| 10 | `services/payment-service` | **Payments Engine** | PostgreSQL | 8010 | `/v1/payments` |
| 11 | `services/marketplace-service` | **Marketplace Engine** | PostgreSQL + search | 8011 | `/v1/marketplace` |
| 12 | `services/medication-service` | **Medication Engine** | PostgreSQL | 8012 | `/v1/medications` |
| 13 | `services/crm-service` | **CRM Engine** | PostgreSQL | 8013 | `/v1/crm` |
| 14 | `services/marketing-service` | **Marketing Automation Engine** | PostgreSQL + Mongo | 8014 | `/v1/marketing` |
| 15 | `services/notification-service` | Push, email, SMS, in-app fan-out | PostgreSQL + Redis | 8015 | `/v1/notifications` |
| 16 | `services/media-service` | Uploads, signed URLs, S3/CloudFront | S3 + PostgreSQL | 8016 | `/v1/media` |
| 17 | `services/ai-orchestrator` | **AI Engine** | Mongo + Redis + vector | 8017 | `/v1/ai` |
| 18 | `services/ml-service` | **ML Engine** | PostgreSQL + vector | 8018 | internal only |
| 19 | `services/provider-success-engine` | **Provider Success (Provider layer)** | PostgreSQL + ClickHouse | **8019** | `/v1/provider-success` |
| 20 | `services/commercial-intelligence-engine` | **Commercial Intelligence (Business layer)** — revenue, pricing, offers, LTV, forecasting | PostgreSQL + ClickHouse | **8020** | `/v1/commercial` |
| 21 | `services/whatsapp-service` | **WhatsApp Communication Engine** | PostgreSQL + Redis | 8086 | `wa.healuxa.com/webhook` |
| 22 | `services/realtime-gateway` | WebSocket fan-out | Redis pub/sub | 8090 | `ws.healuxa.com` |
| 23 | `services/monitoring-service` | Live Ops API + dashboards aggregation | ClickHouse/Timescale | 8095 | `monitoring.healuxa.com` |
| 24 | `apps/web` | Client + marketing PWA (Next.js) | — | 3000 | `app.healuxa.com`, `www.healuxa.com` |
| 25 | `apps/admin-web` | Admin / Live Ops / CRM / Finance / **Commercial Intelligence** dashboards | — | 3001 | `admin.healuxa.com` |
| 26 | `apps/mobile` | Expo / React Native | — | — | App Store / Play |

**Shared infrastructure (Dokploy / managed):** Traefik, PostgreSQL + PgBouncer, Redis (cluster), NATS JetStream, Qdrant (optional), ClickHouse/Timescale, Prometheus, Grafana, Loki, Tempo, Uptime Kuma. MongoDB Atlas + S3/CloudFront are **managed external**.

---

## 6. Project Structure (Multi-Folder, Independently Deployable)

```
healuxa/
├── apps/
│   ├── web/                          # Next.js 15 PWA (client + marketing)   :3000
│   ├── admin-web/                    # Admin + Live Ops + CRM + Finance + Commercial Intelligence :3001
│   └── mobile/                       # Expo / React Native
│
├── services/                         # Each = own Dockerfile, port, Dokploy app
│   ├── transformation-engine/        # PostgreSQL/Mongo (CORE)                :8000
│   ├── identity-service/             # PostgreSQL + Redis (IAM)               :8001
│   ├── profile-service/              # MongoDB                                :8002
│   ├── assessment-service/           # MongoDB                                :8003
│   ├── treatment-service/            # PostgreSQL/Mongo                       :8004
│   ├── provider-service/             # PostgreSQL                             :8005
│   ├── matching-service/             # PostgreSQL + Redis geo                 :8006
│   ├── appointment-service/          # PostgreSQL                             :8007
│   ├── review-service/               # PostgreSQL                             :8008
│   ├── subscription-service/         # PostgreSQL                             :8009
│   ├── payment-service/              # PostgreSQL                             :8010
│   ├── marketplace-service/          # PostgreSQL + search                    :8011
│   ├── medication-service/           # PostgreSQL                             :8012
│   ├── crm-service/                  # PostgreSQL                             :8013
│   ├── marketing-service/            # PostgreSQL/Mongo                       :8014
│   ├── notification-service/         # Redis                                  :8015
│   ├── media-service/                # S3                                     :8016
│   ├── ai-orchestrator/              # Celery + vector                        :8017
│   ├── ml-service/                   # training pipelines                     :8018
│   ├── provider-success-engine/      # PostgreSQL + ClickHouse                :8019
│   ├── commercial-intelligence-engine/ # PostgreSQL + ClickHouse             :8020
│   ├── whatsapp-service/             # Redis                                  :8086
│   ├── realtime-gateway/             # WebSocket                              :8090
│   └── monitoring-service/           # ClickHouse/Timescale                   :8095
│
├── packages/                         # design-system · ts-types · py-common · event-contracts · api-contracts
├── infrastructure/                   # compose · dokploy · traefik · observability · db
├── scripts/                          # seed · migrate · backfill · generate-indexes
└── docs/                             # OpenAPI · ADRs · runbooks · architecture
```

**Per-service folder contract:** `Dockerfile` · `nixpacks.toml` (opt) · `pyproject.toml`/`package.json` · `.env.example` · `src/{main.py,api,domain,infra,events,config.py}` · `migrations/` · `tests/`. `domain/` holds core business logic (in-platform). `main.py` exposes `/health`, `/ready`, `/metrics`.

---

## 7. Polyglot Data Layer Strategy

### 7.1 What goes where

| Store | Data | Why |
|---|---|---|
| **PostgreSQL 16** | Journeys/goals/milestones/outcomes, identity, providers, catalog, appointments, subscriptions, credits, payments, invoices, commissions, reviews, provider-success metrics, **commercial offers/pricing/segments/experiments**, orders, treatment plans, prescriptions, adherence, leads/CRM, audit log | ACID truth |
| **MongoDB Atlas** | Customer/medical/beauty/body profiles, assessments, AI reports, roadmap narratives, conversations, marketing content, ML feature snapshots | Flexible documents |
| **Redis 7 (cluster)** | Sessions/deny-list, OTP, cache, rate limiting, geo index, broker, presence, pub/sub | Sub-ms latency, queueing |
| **S3 + CloudFront** | Photos, before/after, docs, lab PDFs, product media, static | Durable + edge; encrypted (SSE-KMS) |
| **Vector (pgvector → Qdrant)** | Patient memory embeddings, semantic recall | AI long-term memory |
| **NATS JetStream** | Durable domain event log | Async decoupling, replay |
| **ClickHouse / TimescaleDB** | Event analytics, KPIs, **provider performance + commercial intelligence time-series, cohorts, funnels, forecasts** | High-ingest analytics |

### 7.2 Data ownership rule

Each service **owns its tables/collections**. No direct cross-service DB reads — via **API** (sync) or **events** (async, local read-model projections). Analytics engines (Provider Success, Commercial Intelligence, Monitoring) build their own ClickHouse projections from the event stream — they never query other services' primary DBs.

### 7.3 PostgreSQL operational design

PgBouncer pooling; read replicas; partition `appointments`, `payments`, `audit_logs`, `notifications`, `login_history`, `security_events`, `provider_performance` by month; per-service logical DBs (identity + payments isolated first); Alembic migrations in CI/CD.

### 7.4 MongoDB Atlas

CSFLE for medical/PII; UAE-nearest region; backups + PITR; indexes via `scripts/generate_indexes.py`.

### 7.5 Media (S3 + CloudFront)

media-service issues pre-signed S3 URLs; `healuxa-media` (public via CloudFront) + `healuxa-medical` (private, SSE-KMS, signed CloudFront URLs).

---

## 8. Identity Service — Enterprise IAM (Core Platform Service)

> A **custom, enterprise-grade, standalone IAM service** (`services/identity-service`, FastAPI). **No Keycloak, Zitadel, Auth0, or external IAM.** Proven libraries/standards (Argon2id, OAuth2/OIDC patterns, RS256 JWT/JWKS, RFC-6238 TOTP); logic, data, security layer Healuxa-owned. **Own APIs, own database, own security layer**, for **1M+ users**.

### 8.1 Capabilities

| Capability | Description |
|---|---|
| **Authentication** | Email/phone + password (Argon2id), phone/email **OTP**, optional social, magic-link; brute-force lockout |
| **Authorization** | Central policy decision; enforced at edge + per-service via shared SDK |
| **RBAC** | Roles → permissions, per tenant |
| **Fine-grained permissions** | Resource-scoped (`appointments:create`) + ABAC (ownership, tenant, assignment) |
| **JWT (RS256)** | Short-lived access tokens; **JWKS** with key rotation (`kid`) |
| **MFA / OTP** | TOTP, SMS OTP, email OTP, backup codes |
| **Session & Device Management** | Track/list/revoke; "log out everywhere"; device trust + fingerprinting |
| **Login History** | Per-user attempts (success/failure, IP, geo, device, reason) |
| **Audit Logs** | Append-only identity & access actions |
| **Security Event Tracking** | Brute force, impossible travel, new-device, token reuse, MFA failures |
| **API Keys** | Issue/rotate/revoke scoped keys |
| **Service-to-Service Auth** | OAuth2 client-credentials → service JWT; optional mTLS |
| **SSO-like experience** | One login → one token across every service |

### 8.2 Token & session architecture

- **Access token**: RS256 JWT (~15 min), validated **offline** at the edge via **JWKS** (no identity round-trip on hot path → 1M+ scale).
- **Refresh token**: opaque, rotated on use, hashed; **reuse detection** → revoke + security event.
- **Session**: server-side (Postgres + Redis), revocable individually/globally; **denylist** in Redis for near-instant revocation.
- **SSO-like**: shared JWKS + cookie/token domain (`.healuxa.com`); logout → `auth.session_revoked` + denylist.

### 8.3 Enforcement (edge + in-service)

```
Client ──JWT──▶ Traefik ──ForwardAuth──▶ identity-service /v1/auth/introspect (cached)
                  │ inject: X-Healuxa-User, -Roles, -Perms, -Tenant, -Session
                  ▼
            target engine → shared py-common middleware enforces RBAC + ABAC
```

### 8.4 Identity data model (own PostgreSQL DB `identity`)

```sql
users · credentials · mfa_factors · sessions · devices
login_history(... PARTITION BY month) · security_events(... PARTITION BY month)
roles · permissions · role_permissions · user_roles
api_keys · service_clients · consents
audit_logs(... PARTITION BY month) · jwks_keys(kid, public_pem, private_pem_enc, status, rotated_at)
```

### 8.5 APIs

```
POST /v1/auth/register · /login · /logout · /logout-all · /refresh
POST /v1/auth/otp/send · /otp/verify · /verify-phone · /verify-email
POST /v1/auth/password/reset-request · /password/reset · /password/change
POST /v1/auth/mfa/enroll · /mfa/verify · /mfa/challenge · /mfa/backup-codes
GET  /.well-known/jwks.json · POST /v1/auth/introspect · /revoke · /service-token
GET  /v1/sessions · DELETE /v1/sessions/{id} · GET /v1/devices · POST /v1/devices/{id}/trust
GET  /v1/users/{id}/login-history · /security-events · /permissions
GET  /v1/auth/me · GET/PUT /v1/users/{id} · /users/{id}/consent
POST/GET/PUT/DELETE /v1/iam/roles · /iam/permissions · /iam/role-assignments · /iam/api-keys · /iam/service-clients
```

### 8.6 Security layer

Argon2id + pepper; RS256 rotating keys (JWKS); MFA secrets encrypted via KMS/Fernet; Redis rate-limit + lockout; anomaly detection → `security_events` + alerts to Monitoring (§20); optional mTLS; full audit, consent versioning, GDPR export/delete, tenant isolation.

### 8.7 Scale to 1M+

Offline JWKS validation; Redis sessions/denylist/OTP/rate-limit; Postgres read replicas + partitioned history; stateless replicas; identity DB isolated early.

---

## 9. Inter-Service Communication

### 9.1 Synchronous

REST/HTTP+JSON over private `healuxa-net` (`http://transformation-engine:8000`, `http://commercial-intelligence-engine:8020`, …); gRPC for hot paths; timeouts/retries/circuit-breakers/idempotency; S2S auth via service JWT or mTLS; Docker DNS discovery.

### 9.2 Asynchronous (events)

NATS JetStream durable streams (`journey.*`, `provider.*`, `commercial.*`, `appointment.*`, `payment.*`, `subscription.*`, `review.*`, `ai.*`, `ml.*`). The three optimization engines subscribe broadly. JSON-Schema-validated, versioned; replay + DLQ.

### 9.3 Example event flow (triple-layer)

```
appointment.completed
   ├─▶ transformation-engine        → advance milestone + outcome           (customer)
   ├─▶ provider-success-engine      → update provider performance           (provider)
   ├─▶ commercial-intelligence-engine → revenue/LTV/cohort update           (business)
   ├─▶ review-service               → request rating
   └─▶ ml-service                   → training labels (all layers)

subscription.* / payment.*  → commercial-intelligence-engine (revenue, churn-revenue, forecasting)
commercial.upsell_opportunity / commercial.offer_recommended → transformation-engine presents at right moment
commercial.price_suggestion → subscription/marketing engines (dynamic packaging/promotions)
provider.score_updated / provider.capacity_updated → matching-service (ranking)
```

### 9.4 Edge routing (Traefik)

`app/admin.healuxa.com` → web/admin · `api.healuxa.com/v1/<domain>/*` → engine (ForwardAuth) · `ws/wa/monitoring.healuxa.com` → realtime/whatsapp/monitoring.

---

## 10. Core Domain Services

Full data models in §17.

- **10.1 Transformation Engine** — `/v1/journeys` (§3).
- **10.2 Identity Service** — `/v1/auth`, `/v1/users`, `/v1/iam` (§8).
- **10.3 Profile Service** — `/v1/profiles` (Mongo). Emits `profile.updated`.
- **10.4 Assessment Engine** — `/v1/assessments`. Emits `assessment.completed`.
- **10.5 Treatment Service** — `/v1/treatment-plans`. Feeds journey milestones.
- **10.6 Provider Service** — `/v1/providers`, `/v1/services`: typed providers, catalog, availability, geo.
- **10.7 Scheduling Engine (Appointment)** — `/v1/appointments`. Emits `appointment.*`.
- **10.8 CRM Engine** — `/v1/crm`: leads, pipeline, tasks, relationships.

(Marketing, Notification, Media, Subscription, Payment, Marketplace, Medication detailed in §15, §21, §22.)

---

## 11. Provider Matching Engine

> Owned by `matching-service` + `ml-service`, fed by **Provider Success Engine (§13)**. Invoked by the Transformation Engine when a milestone needs a provider.

### 11.1 Inputs (matching factors)

User need/service type · geo proximity (Redis GEO) · **Provider Success Score (§13)** · provider quality score (§12) · **capacity/load (§13)** · availability · specialization fit · service-style fit · ratings/history · price/subscription compatibility · language match.

### 11.2 Algorithm (phased, in-platform)

```python
class MatchingEngine:
    async def rank(self, req):
        candidates = await provider_client.search(...)            # hard filters
        features = await self.assemble_features(candidates, req)  # incl. success score + live capacity
        scores = (await ml_client.rank(features) if FEATURE_ML_RANKING
                  else self.weighted_score(features))
        return self.apply_rules(scores)   # VIP routing, capacity-aware load balance, fatigue

    WEIGHTS = { "provider_success":0.25, "quality_score":0.20, "proximity":0.15,
                "availability":0.12, "capacity":0.08, "specialization_fit":0.10,
                "rating":0.05, "style_fit":0.03, "language_match":0.02 }
```

### 11.3 ML evolution

Phase 1 weighted (explainable) → Phase 2 learning-to-rank → Phase 3 outcome/adherence optimization (Success KPIs §1.2).

### 11.4 Scheduling & APIs — `/v1/matching`

Ranks → appointment-service slots → proposes fastest+best → books atomically → `appointment.created`. Redis GEO; capacity-aware (no over-assignment).
`POST /matching/providers` · `/matching/schedule` · `/matching/book` · `GET /matching/explain/{id}`.

---

## 12. Reviews, Ratings & Provider Quality Score

> Customer ratings + Bayesian **Quality Score**; a key input to Provider Success (§13).

Flow: `appointment.completed` → request rating → client rates overall + dimensions → moderated → `review.created` → Quality Score recomputed (consumed by §13 + Matching).

```python
quality = (C*m + sum(review_scores)) / (C + n)   # Bayesian; recency-weighted; verified-only; penalties
```

APIs — `/v1/reviews`: `POST /reviews` · `GET /reviews/provider/{id}` · `/quality` · `POST /reviews/{id}/moderate` · `GET /reviews/pending`.

---

## 13. Provider Success Engine

> **Provider Success layer** (`services/provider-success-engine`, PostgreSQL + ClickHouse, port **8019**). Continuously optimizes the provider ecosystem and works alongside the Matching Engine (§11).

### 13.1–13.2 Mission & Responsibilities

Maximize provider network health, quality, performance, retention. Responsibilities: **Provider Performance Scoring · Quality Ranking · Capacity Management · Acceptance Rate Tracking · Response Time Monitoring · Customer Satisfaction Analysis · Revenue & Commission Analytics · Lifecycle Management · Retention · Incentive Programs.**

### 13.3 Provider Success Score (composite)

```python
ProviderSuccessScore = weighted_sum({
    "quality_score":0.25, "outcome_contribution":0.20, "acceptance_rate":0.15,
    "response_time":0.10, "satisfaction":0.15, "reliability":0.10, "capacity_health":0.05,
})  # recency-weighted; normalized per type; penalties for complaints/SLA breaches
```

Drives ranking tier, matching weight (§11), incentive eligibility, lifecycle transitions.

### 13.4 Lifecycle

```
onboarding → ramping → active → top_performer
                          └→ underperforming → probation → offboarded  (improves → active)
```

### 13.5 Events

Consumes `appointment.requested|accepted|declined|completed|no_show`, `review.created`, `payment.succeeded`, `commission.computed`, response timings, `journey.milestone_completed`.
Emits `provider.score_updated`, `provider.capacity_updated`, `provider.at_risk`, `provider.lifecycle_changed`, `provider.incentive_awarded`.

### 13.6 Data model (PostgreSQL + ClickHouse)

```sql
provider_performance(provider_id, success_score, quality, outcome_contribution,
                     acceptance_rate, avg_response_seconds, satisfaction, reliability,
                     tier, computed_at)            -- PARTITION BY month
provider_capacity · acceptance_metrics · response_metrics · satisfaction_metrics
revenue_metrics · provider_lifecycle · incentive_programs · incentive_awards
-- high-ingest event time-series in ClickHouse
```

### 13.7 APIs — `/v1/provider-success`

`GET /{id}/score` · `/{id}/capacity` · `/{id}/analytics` · `/ranking` · `/{id}/lifecycle` · `POST /{id}/lifecycle/transition` · `GET/POST /incentives` · `GET /at-risk` · internal `GET /match-signals?ids=...`.

### 13.8 Relationship to Review Engine

Reviews (§12) = voice of the customer (Quality Score). Provider Success = full provider health + economics + lifecycle (combines Quality Score with operational + economic signals).

---

## 14. Commercial Intelligence Engine

> **The Commercial Intelligence layer** (`services/commercial-intelligence-engine`, PostgreSQL + ClickHouse, internal port **8020**, public `/v1/commercial`). The **third core optimization engine**, alongside the Transformation Engine (§3, customer) and Provider Success Engine (§13, provider). It continuously optimizes the **business**: revenue, monetization, pricing, packaging, and growth. Standalone service with its **own database, APIs, and dedicated management dashboard**.

### 14.1 Mission

Maximize **sustainable recurring revenue, LTV, and growth** by turning platform-wide data into commercial decisions — the right **offer**, **price**, **package**, and **moment** for every segment — while feeding the Transformation Engine (when to upsell) and Subscription/Marketing engines (what to price/promote).

### 14.2 Responsibilities

- **Revenue Optimization** — maximize MRR/ARR, margin, net revenue retention across plans, add-ons, marketplace.
- **Dynamic Offers & Packaging** — generate/curate personalized offers and bundles per segment/journey stage.
- **Upsell / Cross-sell Optimization** — uplift modeling to identify who to upsell, to what, and when (feeds Transformation Engine NBA).
- **LTV Analysis** — projected & realized LTV per customer/segment/cohort; CAC:LTV.
- **Cohort Analysis** — retention/revenue/behavior cohorts (acquisition month, plan, segment).
- **Customer Segmentation** — behavioral, value, lifecycle, and luxury-spend segments (RFM + ML clustering).
- **Revenue Forecasting** — time-series forecasts (MRR, churn-revenue, expansion) with confidence intervals.
- **Promotion Performance** — campaign/offer ROI, incremental lift, attribution.
- **Pricing Intelligence** — price elasticity, plan/price testing, packaging recommendations.
- **Business KPI Monitoring** — real-time tracking of the commercial KPIs (§1.2) with alerts on anomalies.

### 14.3 How it fits (third optimization layer)

```
Transformation Engine (customer outcomes) ─┐
Provider Success Engine (provider health) ─┼─▶ shared event bus + ML Engine + ClickHouse
Commercial Intelligence Engine (business) ─┘

Commercial Intelligence:
  • consumes: payment.*, subscription.*, journey.*, appointment.completed,
              marketing.*, review.*, provider.* (revenue)
  • produces: commercial.offer_recommended, commercial.upsell_opportunity,
              commercial.segment_updated, commercial.price_suggestion,
              commercial.forecast_updated, commercial.kpi_alert
  • Transformation Engine acts on offers/upsell at the optimal journey moment.
  • Subscription/Marketing engines apply pricing/packaging/promotions.
```

> **Boundary vs Monitoring (§20):** Monitoring = system + operational health + live event feed. Commercial Intelligence = **business/revenue intelligence + decisions** (offers, pricing, forecasts, segments). They share ClickHouse but serve different audiences and questions.

### 14.4 Intelligence pipeline

```
[events: payments, subscriptions, journeys, appointments, marketing, reviews]
        ▼
[ClickHouse projections]  → revenue ledger, funnels, cohorts, segments, offer ledger
        ▼
[ml-service models]  → forecasting (time-series), segmentation (clustering),
                       upsell uplift, price-elasticity, LTV
        ▼
[decisions]  → dynamic offers, price suggestions, segment assignments, KPI alerts
        ▼
[serving]  → /v1/commercial APIs + dashboard + emitted events
        └────── outcomes (conversions/revenue) loop back as events ──────┘
```

### 14.5 Data model (PostgreSQL + ClickHouse)

```sql
-- PostgreSQL (decisions / config / state)
offers(id, name, type, segment_id, journey_stage, contents JSONB, price_aed,
       discount, valid_from, valid_to, status)
offer_assignments(id, offer_id, user_id, channel, status, presented_at, converted_at)
packages(id, name, plan_ids[], add_ons[], price_aed, target_segment, active)
pricing_rules(id, scope, condition JSONB, suggested_price, elasticity, status)
segments(id, name, definition JSONB, type(rfm|behavioral|value|lifecycle), size, updated_at)
segment_members(segment_id, user_id, score, joined_at)
experiments(id, name, kind(price|offer|package), variants JSONB, metric,
            status, winner, started_at, ended_at)
promotions(id, campaign_id, offer_id, spend_aed, revenue_aed, roi, lift, status)
forecasts(id, metric, horizon, points JSONB, ci_low, ci_high, model_version, generated_at)
kpi_snapshots(id, kpi, value, target, delta, period, captured_at)

-- ClickHouse (high-ingest analytics)
revenue_events · funnel_events · cohort_facts · ltv_facts · offer_events
```

### 14.6 APIs — `/v1/commercial`

```
GET  /commercial/kpis                 # real-time business KPIs (§1.2 commercial)
GET  /commercial/revenue              # MRR/ARR, NRR, by plan/segment/stream
GET  /commercial/forecast?metric=mrr  # forecasts + confidence intervals
GET  /commercial/ltv?by=segment       # LTV analysis
GET  /commercial/cohorts              # retention/revenue cohorts
GET  /commercial/segments · /segments/{id}/members
GET  /commercial/funnels              # conversion funnels
GET  /commercial/promotions           # campaign/offer performance + ROI
GET  /commercial/pricing              # pricing intelligence / elasticity
GET  /commercial/opportunities        # growth opportunities (upsell/cross-sell/expansion)
GET  /commercial/offers/{user}        # personalized dynamic offers
GET  /commercial/upsell/{user}        # upsell/cross-sell recommendations
POST /commercial/offers · /packages · /experiments    # admin authoring
```

### 14.7 Dedicated management dashboard

A **dedicated Commercial Intelligence Center** in `apps/admin-web` (real-time, fed by `/v1/commercial` + WebSocket), giving management live visibility into:

- **Revenue** — MRR/ARR, net revenue retention, revenue by stream/plan/segment.
- **Subscriptions** — active/new/churned, plan mix, upgrade/downgrade flow, credits usage.
- **Retention** — cohort retention curves, churn rate, at-risk revenue.
- **LTV** — LTV by segment/cohort, CAC:LTV, payback period.
- **Conversion funnels** — lead → assessment → subscription → renewal, with drop-off.
- **Campaign performance** — promotion ROI, incremental lift, channel attribution.
- **Forecasts** — MRR/churn/expansion forecasts with confidence bands.
- **Growth opportunities** — ranked upsell/cross-sell/expansion opportunities + recommended actions.

> Drill-downs, date ranges, segment filters, exports; role-restricted (admin/finance/growth) via Identity fine-grained permissions (§8).

---

## 15. Medication & Treatment Adherence

`medication-service` (PostgreSQL): prescriptions (+ dispensing log), adherence schedule + reminders + intake confirmations, adherence score (feeds ML/churn/journey health), refill automation (pharmacy routing → home-visit/marketplace), safety/interaction checks (doctor approval required; guardrails §16).

APIs — `/v1/medications`: `GET /medications` · `POST /{id}/confirm-intake` · `GET /adherence` · `POST /{id}/refill`. Events: `medication.intake_missed`, `medication.refill_due`.

---

## 16. AI / ML Platform & Continuous Learning Loop

### 16.1 AI Orchestrator (`ai-orchestrator`)

Routes to modules (concierge, beauty/body assessment, treatment/roadmap planner, lab summarizer, retention, upsell, churn, risk alerts, follow-up), manages 3-tier memory (Redis → Mongo → vector), enforces guardrails (escalation, doctor-approval-required actions, PII redaction, language, luxury tone), logs/audits everything. LLM adapter (OpenAI + Anthropic, swappable). Human-in-the-loop for clinical outputs.

### 16.2 ML Engine (`ml-service`)

| Model | Purpose |
|---|---|
| Provider ranker (LTR) | Matching (§11) |
| Provider success / churn | Provider Success (§13) |
| Customer churn | Retention (Transformation §3) |
| Next-best-action / upsell uplift | Journey + **Commercial Intelligence (§14)** |
| Recommendation | Services/products personalization |
| Adherence risk | Medication interventions |
| **Forecasting · segmentation · price elasticity · LTV** | **Commercial Intelligence (§14)** |

### 16.3 Continuous Learning Loop

Events (customer + provider + commercial outcomes) → feature store → offline training (Celery) → model registry + versioning → online serving (matching/recommendation/NBA/provider-scoring/forecasting) → A/B + guardrails measuring transformation success, retention, satisfaction, provider success, **commercial KPIs** (§1.2) → results loop back. Only metric-improving models promoted.

---

## 17. Data Models

> PostgreSQL = relational truth; MongoDB = flexible. `tenant_id` everywhere; timestamps + soft-delete. (Identity §8.4; Provider Success §13.6; Commercial Intelligence §14.5.)

### 17.1 PostgreSQL (relational)

```sql
-- transformation-engine
journeys · goals · milestones · phases · next_actions · outcome_records
-- provider-service
providers(id, user_id, type, tenant_id, specialties[], languages[], geo POINT,
          service_style, commission_rate, quality_score, success_score, status)
clinics · services · brands
-- appointment / subscription / payment
appointments(... milestone_id ... )  -- PARTITION BY month
subscriptions · payments(... PARTITION BY month) · invoices · commissions
-- review / treatment / medication / crm
reviews · provider_quality · treatment_plans · treatment_steps
prescriptions(... medications JSONB_ENC ...) · medication_schedule · adherence_log
leads · crm_tasks
```

### 17.2 MongoDB Atlas (flexible)

```javascript
customer_profiles { ..., scores:{health,beauty,churn_risk,upsell,ltv_estimate_aed,lead,luxury_spend}, lifecycle_stage, vip_tier, consent }
medical_profiles · beauty_profiles · body_profiles
assessments · roadmap_narratives · ai_reports · conversations
marketing_campaigns · feature_snapshots
```

---

## 18. Frontend — Web, Admin & Mobile

### 18.1 Web (`apps/web`, Next.js 15) — full parity, journey-centric

App Router + RSC; SSR/ISR for marketing/SEO; **PWA**; luxury UX (tokens, motion, dark/light, RTL); SSO-like auth. The **dashboard centers on the Transformation Journey** (roadmap, goals, milestones, next actions, outcomes), surfacing **personalized offers from Commercial Intelligence (§14)** at the right moment.
Routes: `/`, `/login`, `/onboarding`, `/journey`, `/dashboard`, `/ai-concierge`, `/treatment-plan`, `/appointments`, `/progress`, `/lab-results`, `/medications`, `/marketplace`, `/subscription`, `/invoices`, `/profile`, `/reviews`.
Components: `JourneyRoadmap`, `MilestoneTracker`, `NextActionCard`, `OfferCard`, `WellnessScore`, `TreatmentTimeline`, `BeforeAfterSlider`, `AIConciergeChat`, `MatchPicker`, `AdherenceTracker`, `BookingFlow`.

### 18.2 Admin / Live Ops (`apps/admin-web`)

- **Outcome KPIs first** (customer + provider + commercial, §1.2).
- **Commercial Intelligence Center** (§14.7): revenue, subscriptions, retention, LTV, funnels, campaign performance, forecasts, growth opportunities — real time.
- **Provider Success console**: leaderboard/tiers, at-risk, capacity heatmap, acceptance/response analytics, incentives.
- CRM pipeline, marketing builder, finance/commissions, **Live Ops** (§20), doctor/provider consoles.

### 18.3 Mobile (`apps/mobile`, Expo / RN)

Shares `design-system` + `ts-types`. Native push, camera (signed upload), biometrics, WhatsApp deep links.

---

## 19. Real-Time & Eventing

`realtime-gateway` (WebSocket): AI concierge streaming, journey/milestone updates, appointment status, provider Live Ops, **commercial KPI/offer feeds**, in-app notifications. Redis pub/sub + NATS bridge; scoped, auth-checked topics.

---

## 20. Monitoring & Observability Service

> Dedicated service + stack so management sees the **entire system, transactions, and events live**. (Business/revenue intelligence lives in Commercial Intelligence §14; Monitoring covers system + operational health.)

### 20.1 Stack

Prometheus (metrics) · Grafana (`monitoring.healuxa.com`) · Loki (logs) · Tempo + OpenTelemetry (traces) · Sentry (errors) · Uptime Kuma (`status.healuxa.com`) · ClickHouse/Timescale (business events) · Grafana/Alertmanager alerting.

### 20.2 `monitoring-service`

Subscribes to all domain events → ClickHouse for real-time analytics; `/v1/liveops` APIs + WebSocket for admin: journeys at risk, milestones due, provider success/at-risk + capacity, **commercial KPI alerts**, bookings, payments, AI escalations, churn alerts, per-service health, queue depths, identity security events (§8). Golden signals + SLOs + alerts (payment-failure spike, AI escalation surge, auth anomaly, provider/commercial degradation, service down).

### 20.3 Instrumentation contract

Every service exposes `/health`, `/ready`, `/metrics`, structured JSON logs with `trace_id`, OTel propagation.

---

## 21. Subscriptions, Payments & Marketplace

### 21.1 Subscription plans (AED/month)

| Plan | Price (AED) | Credits |
|---|---|---|
| Essential Beauty | 2,500 | 4 |
| Body Optimization | 3,800 | 6 |
| Skin Glow | 3,200 | 5 |
| Weight Loss Elite | 4,500 | 8 |
| Longevity Executive | 6,500 | 12 |
| Healuxa Black Concierge | 15,000 | Unlimited |

Billing monthly/quarterly/annual; add-ons + credits + wallet; upgrade paths. **Pricing, packaging, and offers are continuously optimized by Commercial Intelligence (§14)**; **renewals orchestrated by the Transformation Engine** (timed to journey phases + retention signals).

### 21.2 Payments

Tap Payments (primary) + Stripe (backup) behind `payment-service`; credits/invoices/commissions/dunning in-platform. Dunning `6h/24h/72h`; failed → CRM + reactivation + journey `at_risk`. Commissions feed Provider Success (§13) and revenue analytics (§14). Invoices → PDF in S3 via signed CloudFront URL.

### 21.3 Marketplace & Brands

`marketplace-service`: products, **global care brands** (curated, tiered), stock, orders, fulfillment, commissions. Search via OpenSearch/Meilisearch; media via CloudFront; fulfillment via home-visit/pharmacy providers. Cross-sell recommendations from Commercial Intelligence (§14).

---

## 22. WhatsApp Automation & Notifications

### 22.1 WhatsApp Communication Engine (`whatsapp-service`)

Meta WhatsApp Business Cloud API; webhook `wa.healuxa.com/webhook`. Flow engine (lead acquisition, onboarding, retention/reactivation, payment/billing, **offer delivery**) often triggered by Transformation/Commercial engine actions. Meta-approved templates + deep links; AI handoff; human escalation on guardrails.

### 22.2 Notification Service (`notification-service`)

Unified fan-out (push, web push, email/SendGrid, SMS/Twilio, in-app, WhatsApp); event-subscribed; channel preferences + quiet hours (Dubai TZ) + consent. Delivers reminders (appointments, medication, billing, milestones), **personalized offers (§14)**, and provider-side notifications (offers, incentives, at-risk nudges).

---

## 23. Scalability & Performance Plan (1M+ Users)

| Concern | Strategy |
|---|---|
| Stateless scaling | N replicas per service; Traefik load-balances |
| DB connections | PgBouncer pooling; per-service caps |
| Read scaling | Postgres read replicas; Redis cache-aside |
| Write scaling | Partition appointments/payments/audit/notifications/login_history/security_events/provider_performance by month; Mongo sharding by `tenant_id`/`user_id` |
| Analytics scaling | ClickHouse for provider + **commercial** + business event time-series, cohorts, funnels, forecasts |
| Caching | Redis cache-aside + CloudFront; HTTP cache + ISR for web |
| Async everything | AI, billing, notifications, ML, journey/provider/**commercial** evaluation off the request path |
| Identity at scale | Offline JWKS validation; Redis sessions/denylist; identity DB isolated early |
| Geo/matching | Redis GEO for sub-ms candidate filtering |
| Rate limiting | Traefik per-IP/token |
| Backpressure | Queue depth monitored; autoscale workers; DLQ |
| Search | Dedicated OpenSearch cluster |
| Cost/latency | UAE/Bahrain region; AI caching; LLM token budgeting |
| Capacity targets | API p95 < 200ms (cached) / < 800ms (uncached); AI first-token < 1.5s; 99.9% uptime SLO |
| Data retention | Hot (Postgres/Redis) → warm (Mongo) → cold (S3) → analytics (ClickHouse) |

---

## 24. Deployment on Dokploy

Each service/app = **separate Dokploy Application** (own Git/monorepo path, Dockerfile/Nixpacks build, port, domain, env). Internal traffic on `healuxa-net`; public TLS-terminated + routed by **Traefik**.

### 24.1 Build strategy

Dockerfile (recommended, multi-stage) / Nixpacks (simple). Local dev via `docker-compose.dev.yml`; prod via Dokploy per-app.

### 24.2 Public domain & route map (Traefik)

| App | Domain / route | Internal port | Build |
|---|---|---|---|
| web | `app.healuxa.com`, `www.healuxa.com` | 3000 | Dockerfile |
| admin-web (incl. Commercial Intelligence Center) | `admin.healuxa.com` | 3001 | Dockerfile |
| API (all backend, incl. journeys, IAM, provider-success, commercial) | `api.healuxa.com/v1/<domain>/*` | per service | Dockerfile |
| realtime-gateway | `ws.healuxa.com` | 8090 | Dockerfile |
| whatsapp-service | `wa.healuxa.com/webhook` | 8086 | Dockerfile |
| monitoring (Grafana) | `monitoring.healuxa.com` | 3002 | image |
| status | `status.healuxa.com` | 3001(kuma) | image |
| media (CDN origin) | `cdn.healuxa.com` (CloudFront) | — | managed |

### 24.3 Internal port allocation (private network)

```
transformation 8000 · identity 8001 · profile 8002 · assessment 8003 · treatment 8004
provider 8005 · matching 8006 · appointment 8007 · review 8008 · subscription 8009
payment 8010 · marketplace 8011 · medication 8012 · crm 8013 · marketing 8014
notification 8015 · media 8016 · ai-orchestrator 8017 · ml 8018 · provider-success 8019
commercial-intelligence 8020 · whatsapp 8086 · realtime 8090 · monitoring 8095
infra: postgres 5432 · pgbouncer 6432 · redis 6379 · nats 4222 · qdrant 6333
       clickhouse 8123/9000 · prometheus 9090 · grafana 3002 · loki 3100 · tempo 3200
```

### 24.4 Traefik routing + centralized auth (per-service labels)

```yaml
# Example labels for commercial-intelligence-engine (Dokploy → Traefik)
- traefik.enable=true
- traefik.http.routers.commercial.rule=Host(`api.healuxa.com`) && PathPrefix(`/v1/commercial`)
- traefik.http.routers.commercial.entrypoints=websecure
- traefik.http.routers.commercial.tls.certresolver=letsencrypt
- traefik.http.routers.commercial.middlewares=healuxa-auth@file,ratelimit@file
- traefik.http.services.commercial.loadbalancer.server.port=8020
```

```yaml
# infrastructure/traefik/dynamic.yml — shared middlewares
http:
  middlewares:
    healuxa-auth:
      forwardAuth:
        address: "http://identity-service:8001/v1/auth/introspect"
        authResponseHeaders: [X-Healuxa-User, X-Healuxa-Roles, X-Healuxa-Perms, X-Healuxa-Tenant, X-Healuxa-Session]
    ratelimit:
      rateLimit: { average: 100, burst: 50 }
```

### 24.5 Local development (`docker-compose.dev.yml`)

```yaml
name: healuxa-dev
networks: { healuxa-net: {} }
services:
  traefik:
    image: traefik:v3.1
    command: ["--providers.docker=true", "--entrypoints.web.address=:80"]
    ports: ["80:80", "8080:8080"]
    volumes: ["/var/run/docker.sock:/var/run/docker.sock:ro"]
    networks: [healuxa-net]
  postgres:
    image: postgres:16-alpine
    environment: { POSTGRES_USER: healuxa, POSTGRES_PASSWORD: dev, POSTGRES_DB: healuxa }
    ports: ["5432:5432"]; volumes: ["pg_data:/var/lib/postgresql/data"]; networks: [healuxa-net]
  redis:      { image: redis:7-alpine, ports: ["6379:6379"], networks: [healuxa-net] }
  nats:       { image: nats:2-alpine, command: ["-js"], ports: ["4222:4222"], networks: [healuxa-net] }
  clickhouse: { image: clickhouse/clickhouse-server:24-alpine, ports: ["8123:8123","9000:9000"], networks: [healuxa-net] }

  commercial-intelligence-engine:
    build: ../../services/commercial-intelligence-engine
    environment:
      - DATABASE_URL=postgresql://healuxa:dev@postgres:5432/commercial
      - CLICKHOUSE_URL=http://clickhouse:8123
      - NATS_URL=nats://nats:4222
      - ML_SERVICE_URL=http://ml-service:8018
      - JWT_PUBLIC_JWKS_URL=http://identity-service:8001/.well-known/jwks.json
    depends_on: [postgres, clickhouse, nats, identity-service]
    networks: [healuxa-net]
    labels:
      - traefik.http.routers.commercial.rule=Host(`api.localhost`) && PathPrefix(`/v1/commercial`)
      - traefik.http.services.commercial.loadbalancer.server.port=8020

  # transformation-engine, provider-success-engine, identity-service + other engines follow the same pattern.
  # MongoDB Atlas + S3 are external (use dev cluster/bucket via .env)
volumes: { pg_data: {} }
```

> **Dev vs prod:** MongoDB Atlas + S3/CloudFront are **managed (external)**. Postgres, Redis, NATS, ClickHouse, observability run as containers locally and as Dokploy services in production.

### 24.6 CI/CD

Push → lint → test → build image per changed service → push to registry → Dokploy deploy hook. Alembic migrations pre-deploy per service. Rolling / blue-green; health checks gate traffic.

---

## 25. Environment Variables (Per Service)

### 25.1 Shared (all backend services)

```env
APP_ENV=production
SERVICE_NAME=commercial-intelligence-engine
LOG_LEVEL=INFO
NATS_URL=nats://nats:4222
REDIS_URL=redis://redis:6379/0
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
SENTRY_DSN=https://...
JWT_PUBLIC_JWKS_URL=http://identity-service:8001/.well-known/jwks.json
SERVICE_AUTH_CLIENT_ID=...
SERVICE_AUTH_CLIENT_SECRET=...
INTERNAL_NETWORK=healuxa-net
TENANT_DEFAULT=healuxa-dubai
```

### 25.2 transformation-engine

```env
DATABASE_URL=postgresql://healuxa:***@pgbouncer:6432/transformation
MONGODB_URI=mongodb+srv://...mongodb.net/healuxa
AI_ORCHESTRATOR_URL=http://ai-orchestrator:8017
ML_SERVICE_URL=http://ml-service:8018
MATCHING_URL=http://matching-service:8006
COMMERCIAL_URL=http://commercial-intelligence-engine:8020
KPI_OBJECTIVE=outcomes_retention_ltv
```

### 25.3 identity-service

```env
DATABASE_URL=postgresql://healuxa:***@pgbouncer:6432/identity
REDIS_URL=redis://redis:6379/0
JWT_PRIVATE_KEY=<RS256 private key>
JWT_ACCESS_TTL=900
JWT_REFRESH_TTL=2592000
ARGON2_MEMORY_COST=65536
ARGON2_TIME_COST=3
PASSWORD_PEPPER=<secret>
MFA_ISSUER=Healuxa
MFA_ENCRYPTION_KEY=<KMS or Fernet key>
OTP_TTL=300
LOGIN_MAX_ATTEMPTS=5
LOCKOUT_SECONDS=900
AWS_KMS_KEY_ID=...
```

### 25.4 provider-success-engine

```env
DATABASE_URL=postgresql://healuxa:***@pgbouncer:6432/provider_success
CLICKHOUSE_URL=http://clickhouse:8123
ML_SERVICE_URL=http://ml-service:8018
REVIEW_URL=http://review-service:8008
PAYMENT_URL=http://payment-service:8010
SUCCESS_SCORE_RECOMPUTE_CRON=*/15 * * * *
INCENTIVE_ENGINE_ENABLED=true
```

### 25.5 commercial-intelligence-engine

```env
DATABASE_URL=postgresql://healuxa:***@pgbouncer:6432/commercial
CLICKHOUSE_URL=http://clickhouse:8123
ML_SERVICE_URL=http://ml-service:8018
SUBSCRIPTION_URL=http://subscription-service:8009
PAYMENT_URL=http://payment-service:8010
MARKETING_URL=http://marketing-service:8014
FORECAST_RECOMPUTE_CRON=0 * * * *
SEGMENTATION_RECOMPUTE_CRON=0 2 * * *
DYNAMIC_OFFERS_ENABLED=true
PRICING_EXPERIMENTS_ENABLED=true
```

### 25.6 profile / assessment / ai (MongoDB)

```env
MONGODB_URI=mongodb+srv://...mongodb.net/healuxa   # Atlas, CSFLE enabled
MONGODB_CSFLE_KEY_VAULT=encryption.__keyVault
AWS_KMS_KEY_ID=...
```

### 25.7 media-service (S3 + CloudFront)

```env
AWS_ACCESS_KEY_ID=... ; AWS_SECRET_ACCESS_KEY=... ; AWS_S3_REGION=me-south-1
S3_BUCKET_PUBLIC=healuxa-media ; S3_BUCKET_MEDICAL=healuxa-medical
CLOUDFRONT_DOMAIN=cdn.healuxa.com ; CLOUDFRONT_KEY_PAIR_ID=... ; CLOUDFRONT_PRIVATE_KEY=... ; SIGNED_URL_TTL=300
```

### 25.8 payment-service

```env
DATABASE_URL=postgresql://healuxa:***@pgbouncer:6432/payments
PAYMENT_GATEWAY=tap_payments ; TAP_SECRET_KEY=sk_... ; TAP_PUBLIC_KEY=pk_... ; STRIPE_SECRET_KEY=sk_... ; CURRENCY=AED
```

### 25.9 ai-orchestrator / ml-service

```env
OPENAI_API_KEY=sk-... ; OPENAI_MODEL=gpt-4o
ANTHROPIC_API_KEY=sk-ant-... ; ANTHROPIC_MODEL=claude-3-7-sonnet
VECTOR_BACKEND=qdrant ; QDRANT_URL=http://qdrant:6333
FEATURE_ML_RANKING=true ; MODEL_REGISTRY_URL=...
```

### 25.10 whatsapp-service

```env
WHATSAPP_API_VERSION=v20.0 ; WHATSAPP_PHONE_NUMBER_ID=... ; WHATSAPP_BUSINESS_ACCOUNT_ID=...
WHATSAPP_ACCESS_TOKEN=... ; WHATSAPP_VERIFY_TOKEN=<webhook-verify-token>
```

### 25.11 web / admin-web

```env
NEXT_PUBLIC_API_URL=https://api.healuxa.com
NEXT_PUBLIC_WS_URL=wss://ws.healuxa.com
NEXT_PUBLIC_CDN_URL=https://cdn.healuxa.com
AUTH_COOKIE_DOMAIN=.healuxa.com
```

### 25.12 Feature flags (shared)

```env
FEATURE_TRANSFORMATION_ENGINE=true
FEATURE_PROVIDER_SUCCESS_ENGINE=true
FEATURE_COMMERCIAL_INTELLIGENCE_ENGINE=true
FEATURE_DYNAMIC_OFFERS=true
FEATURE_PRICING_INTELLIGENCE=true
FEATURE_AI_TREATMENT_PLANS=true
FEATURE_PROVIDER_MATCHING=true
FEATURE_ML_RANKING=true
FEATURE_REVIEWS=true
FEATURE_PROVIDER_INCENTIVES=true
FEATURE_MEDICATION_ADHERENCE=true
FEATURE_HOME_VISITS=true
FEATURE_MARKETPLACE=true
FEATURE_MULTI_LANGUAGE=true
FEATURE_WEB_PARITY=true
```

---

## 26. Implementation Roadmap

| Phase | Scope | Services |
|---|---|---|
| **0 — Foundation** | Repo, CI/CD, Dokploy, Traefik, Postgres/Redis/NATS/ClickHouse, observability, **enterprise Identity**, shared packages | identity, monitoring, infra |
| **1 — Journey core** | **Transformation Engine**, onboarding, profiles, assessments, AI concierge, treatment plans, appointments, web + mobile shells | transformation-engine, profile, assessment, ai-orchestrator, treatment, appointment, provider |
| **2 — Both-sided quality** | Matching (Phase 1 weighted), reviews & quality score, **Provider Success Engine** | matching, review, provider-success-engine, ml (rule-based) |
| **3 — Monetization & commercial** | Subscriptions, payments, invoices, commissions, marketplace + brands, **Commercial Intelligence Engine** (revenue, LTV, cohorts, segmentation, dashboard) | subscription, payment, marketplace, commercial-intelligence-engine |
| **4 — Engagement & ops** | WhatsApp flows, notifications, CRM, marketing, medication adherence, provider incentives, **dynamic offers/pricing**, Live Ops + KPI dashboards | whatsapp, notification, crm, marketing, medication, commercial-intelligence-engine, monitoring |
| **5 — Intelligence** | ML ranking (Phase 2 LTR), churn/NBA/LTV + provider + **forecasting/segmentation/pricing** models, continuous learning loop, A/B + model registry | ml-service, ai-orchestrator, transformation-engine, provider-success-engine, commercial-intelligence-engine |
| **6 — Scale hardening** | Read replicas, partitioning, sharding, autoscaling, SLO/alerting, security audit, load tests to 1M+ | all |

---

*Healuxa Technical Specification v3.3 · Confidential · Dubai, UAE*
