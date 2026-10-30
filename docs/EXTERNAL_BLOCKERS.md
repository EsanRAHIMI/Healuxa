# External Blockers

Items only the owner (or a third party) can resolve. Engineering continues on everything else.

| Blocker | Needed for | Owner action |
|---|---|---|
| GitHub CLI not authenticated on the dev Mac | Opening PRs / reading CI logs from the CLI | Run `gh auth login` (the `git push` credential already works) |
| Dokploy server access (URL, API token or SSH) | Staging/production deployment | Provide access and confirm which projects/domains Healuxa may use |
| Regulatory role determination (DHA licensing, UAE health-data law, PDPL) | Any clinical workflow, real patient data | Legal counsel opinion |
| Health-data residency decision (Atlas region, hosting location) | Storing real customer health data | Decide UAE region / provider after legal review |
| Payment processor merchant account (Stripe UAE / Checkout.com / Network International) | Live payments (sandbox work can proceed once sandbox keys exist) | Open merchant account; provide sandbox keys |
| Apple Developer Program + Google Play Console accounts | Signing, TestFlight, internal testing | Enroll; grant access |
| Reviewed Arabic and Persian translations of consent, medical and payment text | Launch localization | Engage professional medical/legal translators |
| Stripe UAE merchant account + sandbox keys (`sk_test_`, `pk_test_`, webhook `whsec_`) | Running payments against Stripe sandbox; any live payment | Open the Stripe account (AED); provide sandbox keys; live keys only after legal/tax sign-off |
| Accountant review of VAT (rates per line category, healthcare zero-rating, supplier of record for provider/facility fees, invoice wording, rounding) and the seller TRN | Issuing real tax invoices | Engage a UAE tax accountant; register for VAT/TRN |
| Apple Pay / Google Pay domain verification in Stripe | Wallet payments on web | Verify the production domain in the Stripe dashboard |
| Commercial approval of membership plans and pricing | Enabling `MEMBERSHIPS_ENABLED` / `MEMBERSHIP_PAYMENTS_ENABLED` | Owner decision |
| Refund / cancellation policy (24 h full, 50 % inside window) legal review | Customer-facing refunds | Legal review of terms |
