# @healuxa/web

Next.js 16 (App Router) web platform: public site (directory, provider/facility pages, service catalogue,
booking), customer portal, practitioner portal, facility portal and staff console. All data comes from
the Healuxa services through server-side calls (Server Components / Server Actions) using
`@healuxa/api-client`; the browser talks only to this app (and Stripe's hosted payment fields).

## Architecture

| Area | Code | Backend |
|---|---|---|
| Locale routing, CSP nonce, CSRF cookie, silent token refresh | `src/proxy.ts` | identity `/auth/refresh` |
| Session (httpOnly cookies, JWKS-verified JWT) | `src/lib/auth/*` | identity JWKS |
| API clients (one gateway base or per-service URLs) | `src/lib/api.ts`, `src/lib/env.ts` | all |
| Mutations (CSRF-checked, typed error mapping) | `src/actions/*`, `src/lib/actions.ts` | all |
| Public pages | `src/app/[locale]/{providers,facilities,services,book,…}` | provider, appointment |
| Customer portal | `src/app/[locale]/account/*` | identity, appointment, concierge, notification, payment, profile |
| Practitioner / facility portals | `src/app/[locale]/{provider,facility}/*` | provider, appointment |
| Staff console | `src/app/[locale]/admin/*` | provider (`/v1/admin/*`), concierge, payment |

Locales: `en`, `ar`, `fa` (RTL) from `@healuxa/i18n`; tokens from `@healuxa/design-tokens`.

## Run

```bash
npm install                                   # repo root
cp apps/web/.env.example apps/web/.env.local  # set API_BASE_URL (gateway) or per-service URLs
npm run dev -w @healuxa/web                    # http://localhost:3000
npm run build -w @healuxa/web && PORT=3000 npm run start -w @healuxa/web
```

Plain-http local production runs need `AUTH_COOKIE_SECURE=false`.

## Container

```bash
docker build -f apps/web/Dockerfile -t healuxa-web .   # context = repo root
docker run -p 3000:3000 --env-file apps/web/.env.local healuxa-web
```

Standalone output, non-root `node` user, `tini` as PID 1, healthcheck `GET /api/health`
(`/api/health?deep=1` also probes identity + provider for readiness).
