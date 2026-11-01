# Content Rights — App Store Connect answer

**Where:** App Store Connect → your app → **App Information** → **Content Rights** → "Edit".

**Question:** *Does your app contain, show, or access third-party content?*
**Answer:** **Yes, it contains, shows, or accesses third-party content, and I have the necessary rights to that content.**

## Basis for the answer (what the app and backend actually do)

| Content shown in the app | Source | Rights basis |
|---|---|---|
| Practitioner profiles (name, title, biography, specialties, languages; no photos) | Submitted by the practitioner in the Healuxa practitioner portal | Practitioner accepts the Healuxa content publication licence at submission (`accept_content_license`, version + timestamp + account recorded in provider-service) |
| Clinic / hospital profiles, branches, addresses, opening hours, names | Submitted by the facility's administrator in the facility portal | Same licence, accepted by the facility administrator |
| Services and prices | Entered by the practitioner or facility | Same licence |
| Verified-credential summary (authority, type, expiry) | Healuxa's own verification of the licence with DHA / DOH / MOHAP | Healuxa-generated; licence numbers and documents are never shown |
| Healuxa text, design, icons | Healuxa | Owned by Healuxa; icon font Ionicons (MIT licence, bundled via `@expo/vector-icons`) |

- No content is scraped or copied from other directories, websites or medical databases.
- Profiles are **not published** until the licence is accepted — enforced server-side
  (`services/provider-service`: public directory, profile pages, catalogue and booking all require
  `content_license_accepted_at`).
- Rights holders can report any profile in-app ("Report this content" on every practitioner and
  facility page) or via the support e-mail; the in-app **Account → Content rights** screen and the
  website page `/legal/content-rights` explain provenance, licence, verification and removal.

## Note for App Review (paste into *App Review Information → Notes*)

> All practitioner and facility information in Healuxa is submitted by the practitioners and
> facilities themselves through our provider portals. Before any profile is published, its owner
> must accept our content publication licence confirming they own or may share the information and
> granting Healuxa the right to publish it; acceptance (version, time, account) is recorded and
> unaccepted profiles are never shown. Professional licences are verified with the UAE health
> authorities before publication. The policy is in the app under Account → Content rights, and
> every profile has a "Report this content" action.
