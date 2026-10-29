import { TYPE, parse, type MessageFormatElement } from "@formatjs/icu-messageformat-parser";
import { IntlMessageFormat, type PrimitiveType } from "intl-messageformat";

import { DEFAULT_LOCALE, LOCALE_INFO, type Locale } from "./locales";

export type MessageTree = { [key: string]: string | MessageTree };
export type FlatMessages = Record<string, string>;
export type MessageValues = Record<string, PrimitiveType>;

export function flatten(tree: MessageTree, prefix = "", out: FlatMessages = {}): FlatMessages {
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out[path] = value;
    else flatten(value, path, out);
  }
  return out;
}

export interface Translator {
  locale: Locale;
  /** Translate `key` with ICU MessageFormat `values`. Falls back to the default locale, then the key. */
  (key: string, values?: MessageValues): string;
  has(key: string): boolean;
}

export interface TranslatorOptions {
  /** Called for keys missing from both the locale and the fallback catalog. */
  onMissing?: (key: string, locale: Locale) => void;
}

/**
 * Build a translator from pre-shipped catalogs. Catalogs are static files reviewed in git: there is
 * no runtime machine translation anywhere in this package.
 */
export function createTranslator(
  locale: Locale,
  catalogs: Partial<Record<Locale, MessageTree>>,
  { onMissing }: TranslatorOptions = {},
): Translator {
  const primary = flatten(catalogs[locale] ?? {});
  const fallback = locale === DEFAULT_LOCALE ? primary : flatten(catalogs[DEFAULT_LOCALE] ?? {});
  const compiled = new Map<string, IntlMessageFormat>();
  const intl = LOCALE_INFO[locale].intl;

  const t = ((key: string, values?: MessageValues): string => {
    const own = primary[key];
    const source = own ?? fallback[key];
    if (source === undefined) {
      onMissing?.(key, locale);
      return key;
    }
    const cacheKey = own === undefined ? `fallback:${key}` : key;
    let fmt = compiled.get(cacheKey);
    if (!fmt) {
      fmt = new IntlMessageFormat(source, own === undefined ? LOCALE_INFO[DEFAULT_LOCALE].intl : intl, undefined, {
        ignoreTag: true,
      });
      compiled.set(cacheKey, fmt);
    }
    const result = fmt.format(values);
    return typeof result === "string" ? result : String(result);
  }) as Translator;
  t.locale = locale;
  t.has = (key: string) => key in primary || key in fallback;
  return t;
}

/**
 * ICU argument names used by a message, e.g. "{count, plural, one {# item} other {# items}}" ->
 * ["count"]. Throws on syntactically invalid ICU, so tests catch broken translations.
 */
export function placeholdersOf(message: string): string[] {
  const names = new Set<string>();
  const walk = (elements: MessageFormatElement[]): void => {
    for (const el of elements) {
      if (el.type === TYPE.literal || el.type === TYPE.pound) continue;
      if (el.type === TYPE.tag) {
        walk(el.children);
        continue;
      }
      names.add(el.value);
      if (el.type === TYPE.plural || el.type === TYPE.select) {
        for (const option of Object.values(el.options)) walk(option.value);
      }
    }
  };
  walk(parse(message, { ignoreTag: true }));
  return [...names].sort();
}
