import { LAUNCH_LOCALES, getTranslator, isLocale, type Locale, type Translator } from "@healuxa/i18n";
import { notFound } from "next/navigation";

const translators = new Map<Locale, Translator>();

export function getT(locale: Locale): Translator {
  let t = translators.get(locale);
  if (!t) {
    t = getTranslator(locale, {
      onMissing: (key) => {
        if (process.env.NODE_ENV !== "production") console.warn(`[i18n] missing key ${key}`);
      },
    });
    translators.set(locale, t);
  }
  return t;
}

export function isLaunchLocale(value: string): value is Locale {
  return isLocale(value) && (LAUNCH_LOCALES as readonly string[]).includes(value);
}

/** Resolve the `[locale]` route param, 404 for anything that is not a launch locale. */
export async function resolveLocale(params: Promise<{ locale: string }>): Promise<Locale> {
  const { locale } = await params;
  if (!isLaunchLocale(locale)) notFound();
  return locale;
}

/** Pick the best entry of a LocalizedText map ({ en, ar, fa, … }). */
export function localized(text: Record<string, string> | null | undefined, locale: Locale): string | null {
  if (!text) return null;
  return text[locale] ?? text.en ?? Object.values(text)[0] ?? null;
}
