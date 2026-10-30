# payment-service (port 8010)

Payment context (DDD §3.13): server-side quotes, payment intents (automatic or manual capture), void,
full/partial refunds with a cancellation-policy hook, disputes, a double-entry ledger, settlement
import and reconciliation, gap-free tax invoices and credit notes, and the processor side of
memberships. Contract: `packages/api-contracts/openapi/payment.openapi.yaml` (v3.4). Events:
`payment.*`, `commission.computed`. **Sandbox only.**

```bash
scripts/dev/start-infra.sh                     # native Postgres/Redis/NATS (no Docker)
cd services/payment-service
export DATABASE_URL=postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/payment
alembic upgrade head
uvicorn payment_service.main:app --port 8010
```

Tests use `payment_test`: `DATABASE_URL=...payment_test pytest -q` (the fake processor is used; no network).

## Trust rules

- **Amounts never come from the client.** `POST /v1/payment-quotes` prices the subject server side:
  appointments from the provider-service offering (`GET /v1/services/{id}`) of the caller's own
  appointment (read model from `appointment.*` events); memberships from `subscription.created`;
  concierge cases from staff-prepared lines (`payments:manage`). `POST /v1/payments` takes only a quote id
  and requires `Idempotency-Key`.
- **A client "success" screen proves nothing.** State changes only on a verified webhook or on a
  server-side processor response/retrieval (`/refresh`, capture/cancel responses).
- **No card data.** The client confirms with Stripe hosted fields using the PaymentIntent
  `client_secret` (returned only to the paying customer while confirmation is possible, never stored).
  We store processor ids only (`pi_`, `ch_`, `re_`, `dp_`, `cus_`, `sub_`). Events are checked for card
  keys and carry no service names (invoice lines use generic descriptions: "Professional fee", ...).
- **Live mode is impossible** unless `PAYMENTS_LIVE_MODE=true`, an `sk_live_` key and `APP_ENV=production`
  are all set; any live key without the others, the fake processor outside dev/test, or a non-`sk_test_`
  key in sandbox refuse start-up (`config.live_mode_problems`, re-checked when the gateway is built).
  Webhook events whose `livemode` differs from ours are rejected.

## Processor adapter (`PaymentGateway` port, `infra/gateways/`)

- `base.py` — processor-neutral dataclasses + protocol (create/retrieve/capture/cancel payment, refund,
  customer, subscription create/update, balance transactions, payout transactions) and the
  `WebhookTranslator` protocol (verify + translate).
- `stripe.py` — httpx client (form-encoded, `Stripe-Version: 2024-06-20` pinned, `Idempotency-Key` on every
  mutation, 5xx/429/network → retryable `GatewayError`, 4xx → `GatewayRejected`); `Stripe-Signature`
  verification (HMAC-SHA256 over `"{t}.{raw_body}"`, constant-time compare against every `v1`, ±300 s
  tolerance); translation of payment_intent/refund/dispute/invoice/subscription events. No SDK.
- `fake.py` — deterministic in-memory processor with Stripe-shaped objects (so the real Stripe webhook
  translator is exercised in tests), idempotency-key replay, outage injection, fees and payouts.
- Tap Payments is reserved in the contract (`/webhooks/tap_payments` → 404 until an adapter exists).

## Webhooks — `POST /v1/payments/webhooks/stripe`

Raw body verified before parsing → livemode check → processor event id recorded (unique) in the same
transaction as its effects (duplicates acknowledged without reprocessing; a failure rolls back the record
so Stripe's retry runs again) → monotonic state machine (`domain/state.py`): late `payment_failed` after
`succeeded`, or `amount_capturable_updated` after capture, are ignored; same-rank moves need a newer event
timestamp. Unknown objects/types are acknowledged and recorded.

## Ledger, settlement, reconciliation, invoices

- Capture: Dr `processor_clearing` / Cr `provider_revenue`, `facility_revenue`, `healuxa_revenue` (per
  payee id) and `vat_payable`. Refund: proportional reversal (largest-remainder, never exceeding a bucket)
  / Cr `processor_clearing`. Fees and payouts from imported balance transactions; dispute withdrawals to
  `disputes`; differences to `suspense`. Journals are keyed (`capture:<id>`, `refund:<id>`, `fee:<txn>`) so
  postings are idempotent; every journal balances; each payment sums to zero.
- `POST /v1/payments/settlements/import` pulls processor balance transactions and payout membership.
  `GET /v1/payments/reconciliation` flags unknown/missing processor transactions, amount/currency/refund
  mismatches, unbalanced ledgers and payout mismatches.
- Providers/facilities see `GET /v1/payments/settlements/report` for their own revenue lines once finance
  staff link their user to the provider-service payee id (`POST /v1/payments/payees/members`) — ids
  only, no cross-service DB reads; no customer identifiers are exposed.
- Invoices (`INV`) are issued at capture, credit notes (`CN`) at refund. Numbers are gap-free per tenant and
  series (row-locked counter in the issuing transaction). JSON + printable HTML (`/document`); PDF in S3 is
  reserved (`pdf_url`). Seller TRN/name/address come from env placeholders.

## Booking integration (appointment-service, `feat/appointment-service`)

Consumes `appointment.requested|created|accepted|declined|completed|no_show` (current registry). Flow
(confirm-then-charge): booking requested → customer quotes + pays with `capture_method=manual` (default for
appointments) → `payment.authorized` → provider accepts → `appointment.accepted` → capture →
`payment.succeeded` (this **is** the "captured" signal). `appointment.declined` voids the hold
(`payment.canceled`) or fully refunds (`payment.refunded`). The booking engine's `payment_status` hook
should consume `payment.authorized|succeeded|failed|canceled|refunded`, keyed by `subject_type=appointment`,
`subject_id=<appointment_id>`. Cancellation refunds: `GET /v1/payments/{id}/refund-policy?cancelled_at=`
(full ≥ 24 h before, 50 % inside the window, none after start) and `POST /refunds {apply_policy: true}`.
An `appointment.cancelled` event does not exist yet; when the booking engine adds one, wire it to
`apply_policy`. Stripe manual-capture authorisations expire after ~7 days.

## Memberships

Processor subscriptions live here (ACL), plans and membership state in subscription-service.
`subscription.created` → read model → `POST /v1/payment-quotes {subject_type: membership}` →
`POST /v1/payments` creates a Stripe customer + subscription (`default_incomplete`) and returns the first
invoice's client secret. `invoice.paid` / `invoice.payment_failed` → `payment.succeeded` / `payment.failed`
with `subscription_id` and `billing_reason`; `customer.subscription.*` → `payment.billing_agreement_updated`.
`subscription.upgraded|downgraded` re-price and `subscription.cancellation_scheduled` sets
`cancel_at_period_end` at the processor. Disabled until `MEMBERSHIP_PAYMENTS_ENABLED=true`.

## Pending review

VAT rates per line category (`VAT_RATES_BPS`, default 5% everywhere; some healthcare may be zero-rated),
line-level VAT rounding, who is the supplier of record for provider/facility fees, invoice wording and TRN
— all need an accountant (see `docs/EXTERNAL_BLOCKERS.md`).
