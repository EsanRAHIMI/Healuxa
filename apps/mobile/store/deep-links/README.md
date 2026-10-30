# Universal links / App Links — files the web host must serve

The app declares `applinks:healuxa.ae` (iOS associated domains) and an `autoVerify` intent filter
for `https://healuxa.ae/providers*`, `/facilities*`, `/services*` (Android). Verification only
succeeds when `healuxa.ae` serves these files:

| File | URL | Requirements |
|---|---|---|
| `apple-app-site-association` | `https://healuxa.ae/.well-known/apple-app-site-association` | `Content-Type: application/json`, no redirect, no `.json` extension |
| `assetlinks.json` | `https://healuxa.ae/.well-known/assetlinks.json` | `Content-Type: application/json`, no redirect |

Placeholders to replace (owner):

- `APPLE_TEAM_ID` — the Apple Developer team id that owns `ae.healuxa.app`.
- `PLAY_APP_SIGNING_KEY_SHA256_FINGERPRINT` — Play Console → App integrity → App signing key certificate.
- `UPLOAD_KEY_SHA256_FINGERPRINT` — `keytool -list -v -keystore upload.jks` of the upload key.

Paths map 1:1 to app routes (`app/providers/[id].tsx`, `app/facilities/[id].tsx`, `app/(tabs)/services.tsx`),
so the web pages and the app share URLs. Custom scheme links (`healuxa://providers/<id>`) work without
any hosting.
