# Healuxa mobile (iOS + Android)

Expo SDK 57 · React Native 0.86.3 (New Architecture, Hermes) · Expo Router · TypeScript strict.
Bundle id / application id `ae.healuxa.app` (override with `APP_BUNDLE_ID`), scheme `healuxa`,
universal links / App Links for `healuxa.ae` (templates in `store/deep-links/`).

## How the app talks to the backend

| Module | Responsibility |
|---|---|
| `src/api/http.ts` | JSON transport, timeouts, RFC 9457 error parsing (`src/api/errors.ts`) |
| `src/api/client.ts` | The only API surface screens use; every method names its OpenAPI `operationId` |
| `src/auth/sessionManager.ts` | Sign-in/register, refresh-token rotation (single flight), 401 retry, sign-out (+ hooks) |
| `src/auth/tokenStore.ts` | Keychain/Keystore persistence (`expo-secure-store`, this-device-only); never AsyncStorage |
| `src/auth/AuthProvider.tsx` | React state for the session + optional biometric lock (`expo-local-authentication`) |
| `src/cache/publicCache.ts` | Offline cache for public directory content only; refuses authenticated/health data |
| `src/notifications/push.ts` | Push permission → native APNs/FCM token → notification-service registration |
| `src/i18n/` | en / ar / fa catalogs, RTL via `I18nManager` (restart applied with `reloadAppAsync`) |

| Screen | Backend operations |
|---|---|
| Home | provider `searchProviders`, notification `getUnreadNotificationCount` |
| Directory | provider `searchProviders`, `searchFacilities` |
| Provider profile | provider `getProvider`, `listServices(provider_id)`, `getFacility` |
| Facility | provider `getFacility`, `listBranches`, `getOperatingHours`, `listServices(facility_id)` |
| Services | provider `listServices` |
| Book / reschedule | provider `getServiceOffering`; appointment `listAvailableSlots`, `createAppointment` (hold), `transitionAppointment` (submit / cancel), `rescheduleAppointment` |
| Bookings, booking detail | appointment `listAppointments`, `getAppointment`, `listAppointmentTransitions`, `transitionAppointment(cancel)` |
| Concierge | concierge `listMyConciergeCases`, `createConciergeCase`, `getConciergeCase`, `listConciergeCaseOptions`, `selectConciergeCaseOption`, `listConciergeCaseMessages`, `postConciergeCaseMessage`, `markConciergeCaseMessagesRead`, `transitionConciergeCase(cancelled)` |
| Notifications | notification `listNotifications`, `markNotificationRead`, `markAllNotificationsRead` |
| Notification settings | notification `getPreferences`, `updatePreferences`, `registerDeviceToken`, `deleteDeviceToken` (on sign-out) |
| Sign in / register / account | identity `authLogin`, `authRegister`, `authRefresh`, `authLogout` |
| Sessions | identity `listSessions`, `revokeSession` |
| Delete account | identity `authDeleteAccount` (password re-confirmation), then local session wipe |

Base URL: one `EXPO_PUBLIC_API_BASE_URL` pointing at the production nginx gateway
(`infrastructure/production/gateway/nginx.conf` routes `/v1/*` to each service; default
`https://api.healuxa.ae`), with optional per-service `*_BASE_URL` overrides for local dev. Non-local builds
(`APP_ENV=staging|production`) fail to build with a non-https URL. Local builds default to
`localhost:8201/8205/8207/8221/8222` (Android emulator rewritten to `10.0.2.2`).

## Run locally

```bash
npm install                                  # repo root (npm workspaces)
apps/mobile/scripts/e2e-backends.sh          # identity, provider, appointment, concierge, notification
node apps/mobile/e2e/seed.mjs                # synthetic directory data (local DBs only)
cd apps/mobile
npx expo prebuild                            # generates ios/ and android/ (not committed)
npx expo run:ios                             # or: npx expo run:android
```

## Build

`ios/` and `android/` are generated (Continuous Native Generation) locally and in CI; edit
`app.config.ts` / `plugins/` instead of native files.

```bash
APP_ENV=production npx expo prebuild --clean
# iOS simulator
xcodebuild -workspace ios/Healuxa.xcworkspace -scheme Healuxa -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' build
# iOS release compile proof (no signing)
xcodebuild -workspace ios/Healuxa.xcworkspace -scheme Healuxa -configuration Release -sdk iphoneos \
  -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO build
# Android
(cd android && ./gradlew assembleDebug && ./gradlew bundleRelease)
```

## Signing and release (owner)

- **Android:** create an upload keystore (never commit it) and provide `HEALUXA_UPLOAD_STORE_FILE`,
  `HEALUXA_UPLOAD_STORE_PASSWORD`, `HEALUXA_UPLOAD_KEY_ALIAS`, `HEALUXA_UPLOAD_KEY_PASSWORD` as env
  vars or in `~/.gradle/gradle.properties` (CI: `HEALUXA_UPLOAD_KEYSTORE_BASE64` + the three
  secrets). Without them `bundleRelease` is debug-signed and must not be uploaded.
- **iOS:** Apple Developer team, App ID `ae.healuxa.app` with Associated Domains and Push, then
  archive in Xcode or with EAS (`eas.json` profiles are prepared; nothing has been submitted).
- Store metadata, privacy answers, permission texts and review notes: `store/`.

## Tests

`npm test -w @healuxa/mobile` (Jest + React Native Testing Library). Detox smoke:
`npx detox build -c ios.sim.release && npx detox test -c ios.sim.release` with the local backends.
