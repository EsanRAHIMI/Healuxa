import ar from "../messages/ar.json";
import de from "../messages/de.json";
import en from "../messages/en.json";
import fa from "../messages/fa.json";
import fr from "../messages/fr.json";
import type { Locale } from "./locales";
import { createTranslator, type MessageTree, type Translator, type TranslatorOptions } from "./translator";

export * from "./locales";
export * from "./format";
export { createTranslator, flatten, placeholdersOf, type FlatMessages, type MessageTree, type MessageValues, type Translator } from "./translator";

/** Shipped catalogs. fr/de are partial scaffolding and fall back to English per key. */
export const catalogs: Record<Locale, MessageTree> = { en, ar, fa, fr, de } as Record<Locale, MessageTree>;

export function getTranslator(locale: Locale, options?: TranslatorOptions): Translator {
  return createTranslator(locale, catalogs, options);
}
