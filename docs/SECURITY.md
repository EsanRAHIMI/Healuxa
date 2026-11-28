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
| Medical records: owner-only management; grantee reads only via an active, unexpired grant **and** a per-request provider-service membership check (fails closed); no platform-staff path; 404 for unrelated records | `profile_service/domain/records.py` | `test_records_grants.py`, `test_records_directory_http.py` |
| Record files: type from magic bytes (PDF/JPEG/PNG), size cap, sanitised names, AES-256-GCM per file (random nonce, key id, AAD bound to tenant+record), attachment + nosniff download, byte deletion | `profile_service/domain/files.py`, `infra/crypto.py`, `infra/storage.py` | `test_records_upload.py` |
| Append-only record access log incl. refused attempts; record events carry ids only | `profile_service/domain/records.py` | `test_records_grants.py`, `test_records_events_erasure.py` |
| Atomic event staging (no lost or phantom events) | outbox | py-common + service outbox tests, outage drill |

## Known gaps (tracked)

- Traefik ForwardAuth with edge secret not built; until then the edge must strip `X-Healuxa-*`.
- MFA enrolment flows exist in identity schema but privileged-account MFA enforcement is not yet
  required at login.
- Dependency/secret scanning, SAST, SBOM in CI: not yet added.
- MongoDB client-side field-level encryption (CSFLE) settings exist but are not enabled.
- Provider credential documents still have no upload; customer medical records use encrypted GridFS
  behind a storage port until object storage is approved (S3-compatible backend not built).
- Records encryption key lives in an env var (no KMS/envelope encryption yet); rotation re-reads via
  `RECORDS_RETIRED_KEYS` but there is no re-encryption job.
- Rate limiting is expected at the edge; services do not rate-limit themselves (except login lockout).
