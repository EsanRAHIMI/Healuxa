# Permission justifications

| Permission | Platform key | Requested when | User-facing justification |
|---|---|---|---|
| Face ID | iOS `NSFaceIDUsageDescription` | Only after the user turns on Account → Biometric unlock | "Healuxa uses Face ID to unlock your signed-in session on this device when you turn on biometric unlock." |
| Biometrics | Android `USE_BIOMETRIC`, `USE_FINGERPRINT` (normal permissions, no prompt) | Same | Same text in the in-app explanation |
| Notifications | iOS authorization request / Android 13+ `POST_NOTIFICATIONS` | Only from Account → Notifications, only when the `FEATURE_PUSH=1` flag is on (off by default) | "Get updates about your requests and appointments." |
| Internet | Android `INTERNET` | Always (normal permission) | Required to load the directory and sign in |

Explicitly **blocked** in the Android manifest (`app.config.ts → android.blockedPermissions`):
`SYSTEM_ALERT_WINDOW`, `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, `RECORD_AUDIO`.

Not used: location, camera, photos, contacts, microphone, calendar, tracking (no ATT prompt).

`LSApplicationQueriesSchemes = [mailto]` lets the deletion screen check that a mail app exists
before opening the pre-filled deletion request.
