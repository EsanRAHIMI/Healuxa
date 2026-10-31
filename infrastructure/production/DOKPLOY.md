# Dokploy production deployment

Use Git source `https://github.com/EsanRAHIMI/Healuxa.git`, repository-root build context,
and Compose Path `./compose.dokploy.yml`. This entry point contains the existing 15 long-running
components and eight one-shot migration jobs. Mobile binaries are built separately; they are not
server containers.

The original `infrastructure/production/docker-compose.yml` remains available for operators managing
the individual env files themselves. The Dokploy entry point instead reads explicit variables from
the Environment tab, builds configuration files into the PostgreSQL/gateway images, and requires no
host bind mounts into the disposable Git checkout.

## Before first deployment

1. Use a **new** production stack and new named volumes. The PostgreSQL image provisions eight
   databases with independent owner roles on first initialization. It does not convert an existing
   shared-role database. Never use Fresh Volumes to repair a production deployment.
2. Fill `dokploy.env.example` in Dokploy's Environment tab. Generate independent random hex values
   for the database passwords, service credential, pepper and encryption key; use at least 32 random
   bytes each. Hex passwords avoid URL-encoding ambiguity in `DATABASE_URL`.
3. Supply production Atlas connections for `PROFILE_MONGODB_URI` and `ASSESSMENT_MONGODB_URI`,
   with separate users restricted to `healuxa_profile` and `healuxa_assessment`. Replica-set
   transactions are required. Do not reuse the local `_test` databases.
4. Set actual Stripe account keys and webhook signing secret, plus an explicit `PAYMENTS_LIVE_MODE`.
   Live mode requires live keys. Never fill placeholder keys merely to make startup validation pass.
   Set the real seller/invoice configuration before enabling real transactions.
5. Keep the backend and datastore services detached from `dokploy-network` in Dokploy Advanced →
   Networks. Only `web` and `gateway` join that network; all components share the private,
   Compose-project-scoped `healuxa` network. No host ports are published.
6. Route `healuxa.ae` (and optionally `www.healuxa.ae`) to `web:3000`, and `api.healuxa.ae` to
   `gateway:8080`, with HTTPS. Match DNS to the selected deployment server. The web base URL is
   `http://gateway:8080/v1`; identity issuer is `https://api.healuxa.ae`.

Leave `JWT_PRIVATE_KEY_PEM` absent to use identity's database-managed signing keys. An empty variable
is not equivalent to absence: the production configuration guard rejects it.

## Verify and operate

Check deployment logs, all migration jobs exit 0, every backend `/ready`, and
`/api/health?deep=1` on web. Then exercise registration/sign-in and a real catalog-to-slot request.
Verify `/v1/auth/service-token`, `/v1/auth/introspect`, `/v1/internal/*` and `/metrics` remain blocked
at the public gateway. A successful Compose config check alone does not prove runtime readiness.

Set up encrypted backups of the PostgreSQL and NATS named volumes and the Atlas databases, and test
a restore. Preserve the pepper, encryption key and service secret across redeployments. Start with
one Python worker to avoid concurrent first-start initialization; tune capacity from measurements.

Missing Atlas or Stripe credentials are deployment blockers, not a reason to switch `APP_ENV` to
development, use a fake payment gateway, or publish partially configured services.
