# App Review notes — DRAFT

> Replace every `<…>` before submitting. Do not commit real credentials to this repository; enter
> the demo account only in App Store Connect → App Review Information.

**Demo account**

- Username: `<owner creates a dedicated review account on production — not created by engineering>`
- Password: `<entered in App Store Connect only>`

**What to review**

1. The public directory (Directory tab) works without an account and lists only practitioners whose
   licence has been verified by Healuxa staff.
2. A provider profile shows the verified credential summary (authority and expiry, never licence
   numbers) and each service's total price with the professional fee and facility fee separately.
3. Account tab → sign in with the demo account → Devices and sessions lets the user sign out any
   device.
4. **Account deletion** (Guideline 5.1.1(v)): Account → Delete account → enter the password →
   confirm. The account is deleted immediately (identity-service `POST /v1/auth/delete-account`):
   sign-in removed, all sessions revoked, other services erase or anonymise the user's data.
5. Biometric unlock (Account → Biometric unlock) is optional; Face ID is only requested after the
   user turns it on.

**Medical disclaimer** — Healuxa is a directory and concierge service; it does not diagnose or
treat. Practitioners are independently licensed by DHA / DOH / MOHAP.

**Contact** — `<review contact name, phone, email>`
