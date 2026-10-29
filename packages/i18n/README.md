# @healuxa/i18n

Static message catalogs (`messages/{en,ar,fa,fr,de}.json`, ICU MessageFormat), locale metadata
(RTL for ar/fa) and Intl formatting helpers. No runtime machine translation.

```ts
import { getTranslator, formatMoney, formatWallTime, weekdayName, dirOf, negotiateLocale } from "@healuxa/i18n";
const t = getTranslator("ar");
t("common.results", { count: 3 });
formatMoney(125050, "AED", "ar");          // amounts are integer minor units (fils)
formatWallTime("09:00", "fa");             // branch-local wall-clock times from the API
```

- Launch locales: en, ar, fa — `npm test` fails if ar/fa miss any English key or change ICU placeholders.
- fr/de: scaffolding; missing keys fall back to English per key.
- `manifest.json` flags `legal.*`, `consent.*`, `clinical.*`, `payment.*` (and `extra_keys`) as
  `needs_professional_review`; ar/fa are `machine_draft`. Run `npm run manifest -w @healuxa/i18n` after
  adding keys. Put any new legal/clinical/consent/payment copy in those namespaces.
