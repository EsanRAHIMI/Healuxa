# Release Checklist

Tick only with evidence (CI run id, commit, test output, measurement). Unticked items block launch.

## Code (this repository)
- [ ] All CI workflows green on the release commit (`CI`, `Images`)
- [ ] All migrations round-trip (`alembic downgrade base && alembic upgrade head`) — enforced in CI
- [ ] No model/migration drift (`alembic check`) — enforced in CI for provider-service
- [ ] Critical journeys pass end-to-end tests (web E2E job)
- [ ] Booking concurrency test passes (appointment-service)
- [ ] Payment sandbox flows pass (payment-service — not built)
- [ ] Lighthouse/axe results recorded in `docs/PERFORMANCE.md`
- [ ] iOS and Android release builds succeed (mobile — not built)
- [ ] `docs/DEPLOYMENT_HANDOFF.md` matches the services in this commit

## Deployment (deployment agent)
- [ ] Staging deployed from the release commit; `/ready` green on all services
- [ ] Edge strips `X-Healuxa-*`; forged-header probe returns 401
- [ ] Backups configured and a restore tested
- [ ] Monitoring/alerts on `/ready`, outbox backlog, `dead_lettered` events
- [ ] Production promotion approved by the owner

## External (owner)
- [ ] Items in `docs/EXTERNAL_BLOCKERS.md` resolved or explicitly accepted
- [ ] Reviewed translations for consent, medical and payment text
- [ ] Store accounts, signing, privacy declarations (mobile)
