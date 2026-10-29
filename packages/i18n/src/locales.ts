export const LOCALES = ["en", "ar", "fa", "fr", "de"] as const;
export type Locale = (typeof LOCALES)[number];

/** Locales served publicly at launch (UAE). fr/de are scaffolding for the European expansion. */
export const LAUNCH_LOCALES = ["en", "ar", "fa"] as const satisfies readonly Locale[];
export const SCAFFOLD_LOCALES = ["fr", "de"] as const satisfies readonly Locale[];
export const DEFAULT_LOCALE: Locale = "en";

export type Direction = "ltr" | "rtl";
export type Script = "latin" | "arabic" | "persian";

export interface LocaleInfo {
  code: Locale;
  /** Name in its own language, for the language switcher. */
  nativeName: string;
  dir: Direction;
  script: Script;
  /** BCP 47 tag used for Intl formatting (region defaults to the launch market). */
  intl: string;
  /** Open Graph locale. */
  og: string;
}

export const LOCALE_INFO: Record<Locale, LocaleInfo> = {
  en: { code: "en", nativeName: "English", dir: "ltr", script: "latin", intl: "en-AE", og: "en_AE" },
  ar: { code: "ar", nativeName: "العربية", dir: "rtl", script: "arabic", intl: "ar-AE", og: "ar_AE" },
  fa: { code: "fa", nativeName: "فارسی", dir: "rtl", script: "persian", intl: "fa-IR", og: "fa_IR" },
  fr: { code: "fr", nativeName: "Français", dir: "ltr", script: "latin", intl: "fr-FR", og: "fr_FR" },
  de: { code: "de", nativeName: "Deutsch", dir: "ltr", script: "latin", intl: "de-DE", og: "de_DE" },
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function dirOf(locale: Locale): Direction {
  return LOCALE_INFO[locale].dir;
}

/**
 * Pick the best supported locale from an Accept-Language header (RFC 9110 q-values).
 * Only `available` locales are considered (defaults to the launch set).
 */
export function negotiateLocale(
  acceptLanguage: string | null | undefined,
  available: readonly Locale[] = LAUNCH_LOCALES,
  fallback: Locale = DEFAULT_LOCALE,
): Locale {
  if (!acceptLanguage) return fallback;
  const ranked = acceptLanguage
    .split(",")
    .map((part, index) => {
      const [tag = "", ...params] = part.trim().split(";");
      const q = params.map((p) => p.trim()).find((p) => p.startsWith("q="));
      const quality = q ? Number.parseFloat(q.slice(2)) : 1;
      return { tag: tag.toLowerCase(), quality: Number.isFinite(quality) ? quality : 0, index };
    })
    .filter((x) => x.tag && x.quality > 0)
    .sort((a, b) => b.quality - a.quality || a.index - b.index);
  for (const { tag } of ranked) {
    const base = tag.split("-")[0];
    const hit = available.find((l) => l === tag || l === base);
    if (hit) return hit;
  }
  return fallback;
}
