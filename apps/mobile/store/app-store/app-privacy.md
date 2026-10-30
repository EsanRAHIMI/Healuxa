# App Privacy ("nutrition label") answers — DRAFT

Basis: the code in `apps/mobile` at this commit. Re-check before every submission. The privacy
manifest (`PrivacyInfo.xcprivacy`) is generated from `ios.privacyManifests` in `app.config.ts`;
third-party SDK manifests (Expo modules, React Native) are merged by Xcode.

**Tracking:** No. The app contains no advertising SDK, no analytics SDK, no IDFA access and no
cross-app tracking. `NSPrivacyTracking = false`, no tracking domains.

## Data collected

| Apple category | Data type | Collected? | Linked to user | Tracking | Purpose | Where |
|---|---|---|---|---|---|---|
| Contact Info | Email Address | Yes (if user registers with email) | Yes | No | App Functionality (account) | identity-service `authRegister` / `authLogin` |
| Contact Info | Phone Number | Yes (if user registers with a phone number) | Yes | No | App Functionality | same |
| Identifiers | User ID | Yes | Yes | No | App Functionality | account id issued by identity-service |
| Usage Data / Diagnostics | — | **No** | — | — | — | no crash/analytics SDK is bundled |
| Health & Fitness | Health | **No** (this version) | — | — | — | the app does not collect assessments, symptoms or medical records yet |
| Location | — | No | — | — | — | directory search uses a city filter only |
| Contacts, Photos, Audio, Browsing, Search history, Financial, Purchases | — | No | — | — | — | — |

Notes for the owner:

- Server-side the identity service records the **IP address** of sign-ins (sessions list). Apple
  treats IP collected for security as not "collected" only if it is not linked/retained beyond
  that purpose — confirm the retention policy, otherwise declare *Identifiers → Device ID / Other*.
- When booking, assessments or push notifications ship, this file must be updated (Health data,
  Device ID for push tokens, Purchase history).
- Account deletion: offered in-app (Account → Delete account). Today it creates an email request
  because identity-service has no deletion endpoint — see `docs/EXECUTION_LEDGER.md` (mobile).

## Required-reason APIs declared (privacy manifest)

| API category | Reason | Why |
|---|---|---|
| File timestamp | C617.1 | public directory cache files in the app container |
| UserDefaults | CA92.1 | React Native / Expo module settings in the app's own defaults |
| System boot time | 35F9.1 | React Native performance timing (elapsed time) |
| Disk space | E174.1 | Expo file-system checks before writing cache files |
