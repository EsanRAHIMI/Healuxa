# Google Play Data safety form — DRAFT

Package: `ae.healuxa.app`. Basis: `apps/mobile` at this commit (no ads, analytics or crash SDKs).

## Overview answers

| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | Yes (collect); **no sharing** |
| Is all of the user data collected by your app encrypted in transit? | Yes — production builds refuse non-HTTPS base URLs (`app.config.ts`), Android cleartext is disabled outside local dev/E2E builds |
| Do you provide a way for users to request that their data is deleted? | Yes — in-app: Account → Delete account (email request today); web: `<https://healuxa.ae/account-deletion — owner must publish this page, Play requires a web URL>` |

## Data types

| Category | Type | Collected | Shared | Optional? | Purpose | Ephemeral? |
|---|---|---|---|---|---|---|
| Personal info | Email address | Yes | No | Required to create an account (browsing needs none) | Account management | No |
| Personal info | Phone number | Yes (if used as identifier) | No | Optional alternative to email | Account management | No |
| Personal info | User IDs | Yes | No | Required for accounts | Account management | No |
| App activity, Location, Health and fitness, Financial, Messages, Photos, Audio, Files, Calendar, Contacts, Web browsing, Device IDs, App info and performance | — | **No** | — | — | — | — |

Notes:

- Push notifications are behind a feature flag and **off** in this build; when enabled, the FCM
  token is a *Device or other ID* (App functionality) and must be added here.
- Server-side IP addresses of sign-ins are stored for security (sessions list) — declare under
  *Device or other IDs* if retained beyond fraud prevention (owner/legal decision).
- Health data is not collected in this version.
