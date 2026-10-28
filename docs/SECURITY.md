# Security

Baselines: OWASP ASVS (API/web), OWASP API Security Top 10, OWASP MASVS (mobile, when built).
This page lists controls that exist and are **tested**, then known gaps. It is not a compliance claim.

## Implemented and tested

| Control | Where | Evidence |
|---|---|---|
| Identity headers trusted only with edge secret; otherwise bearer introspection | `py-common/middleware/auth.py` | `test_edge_trust.py`, per-service `test_forged_identity_headers.py` |
| RBAC permissions from identity roles; ABAC ownership/role checks in services | identity migrations 0002–0007; `provider_service/domain/access.py` | provider-service tests (owner vs staff vs facility role vs stranger) |
| Tenant isolation on every query | all services | `provider-service/tests/test_security.py` |
| No existence leaks: unauthorised reads of private resources return 404 | provider-service | onboarding/affiliation tests |
| Public views redact credential numbers, license numbers, owner ids | provider-service | `test_public_directory.py` |
| Password hashing (Argon2 + pepper), account lockout, refresh-token reuse detection revoking all sessions | identity-service | identity tests |
| Production refuses missing/default secrets; settings errors never echo values | `py-common/config.py` | `test_production_settings.py` |
| Events never carry credential numbers or health data | event schemas, publishers | outbox tests |
| Non-root containers, healthchecks, no secrets in build context | Dockerfiles, `.dockerignore` | `images.yml` |
| Atomic event staging (no lost or phantom events) | outbox | py-common + service outbox tests, outage drill |

## Known gaps (tracked)

- Traefik ForwardAuth with edge secret not built; until then the edge must strip `X-Healuxa-*`.
- MFA enrolment flows exist in identity schema but privileged-account MFA enforcement is not yet
  required at login.
- Dependency/secret scanning, SAST, SBOM in CI: not yet added.
- MongoDB client-side field-level encryption (CSFLE) settings exist but are not enabled.
- Document upload (credential documents) needs object storage with encryption; not built.
- Rate limiting is expected at the edge; services do not rate-limit themselves (except login lockout).
