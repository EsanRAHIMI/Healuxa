/**
 * Locale-aware formatting on top of Intl (available in browsers, Node and Hermes/React Native).
 * Money is always handled in integer minor units, as the APIs return it.
 */
import { LOCALE_INFO, type Locale } from "./locales";

const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat | Intl.ListFormat>();

function memo<T extends Intl.NumberFormat | Intl.DateTimeFormat | Intl.ListFormat>(key: string, make: () => T): T {
  let hit = cache.get(key) as T | undefined;
  if (!hit) {
    hit = make();
    cache.set(key, hit);
  }
  return hit;
}

export function intlLocale(locale: Locale): string {
  return LOCALE_INFO[locale].intl;
}

/** Number of minor-unit digits for a currency (AED: 2 fils per … 100 fils = 1 dirham). */
export function currencyExponent(currency: string): number {
  return new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
}

export interface MoneyFormatOptions {
  /** "symbol" renders e.g. "AED 1,250.00" in en-AE and "‏1,250.00 د.إ.‏" in ar-AE. */
  display?: "symbol" | "code" | "name";
  /** Drop ".00" for whole amounts. */
  trimWholeUnits?: boolean;
}

export function formatMoney(
  amountMinor: number,
  currency: string,
  locale: Locale,
  { display = "code", trimWholeUnits = false }: MoneyFormatOptions = {},
): string {
  if (!Number.isInteger(amountMinor)) throw new TypeError("amountMinor must be an integer number of minor units");
  const exponent = currencyExponent(currency);
  const major = amountMinor / 10 ** exponent;
  const whole = amountMinor % 10 ** exponent === 0;
  const digits = trimWholeUnits && whole ? 0 : exponent;
  const fmt = memo(`money|${locale}|${currency}|${display}|${digits}`, () =>
    new Intl.NumberFormat(intlLocale(locale), {
      style: "currency",
      currency,
      currencyDisplay: display,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }),
  );
  return fmt.format(major);
}

export function formatNumber(value: number, locale: Locale, options: Intl.NumberFormatOptions = {}): string {
  return memo(`num|${locale}|${JSON.stringify(options)}`, () => new Intl.NumberFormat(intlLocale(locale), options)).format(value);
}

function toDate(value: Date | string | number): Date {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) throw new RangeError(`Invalid date: ${String(value)}`);
  return d;
}

/**
 * Format an instant. Pass the branch's IANA `timeZone` for anything location-bound (opening hours,
 * availability) so users see branch-local time, not their device time.
 */
export function formatDateTime(
  value: Date | string | number,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" },
): string {
  return memo(`dt|${locale}|${JSON.stringify(options)}`, () => new Intl.DateTimeFormat(intlLocale(locale), options)).format(
    toDate(value),
  );
}

export function formatDate(value: Date | string | number, locale: Locale, options: Intl.DateTimeFormatOptions = { dateStyle: "medium" }): string {
  // Bare ISO dates (YYYY-MM-DD) are calendar dates: format them in UTC so they never shift a day.
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return formatDateTime(`${value}T00:00:00Z`, locale, { ...options, timeZone: "UTC" });
  }
  return formatDateTime(value, locale, options);
}

/**
 * "09:00" (24h wall-clock string from the API) -> localized time label, e.g. "9:00 AM".
 * "24:00" (end of day, allowed as a closing time) renders as midnight.
 */
export function formatWallTime(hhmm: string, locale: Locale): string {
  const m = /^(\d{2}):(\d{2})$/.exec(hhmm);
  if (!m) return hhmm;
  const hours = Number(m[1]) % 24;
  const minutes = Number(m[2]);
  return formatDateTime(Date.UTC(2024, 0, 1, hours, minutes), locale, { hour: "numeric", minute: "2-digit", timeZone: "UTC" });
}

/** ISO weekday used by the APIs: 0 = Monday … 6 = Sunday. */
export function weekdayName(isoWeekday: number, locale: Locale, width: "long" | "short" = "long"): string {
  // 2024-01-01 was a Monday.
  return formatDateTime(Date.UTC(2024, 0, 1 + isoWeekday), locale, { weekday: width, timeZone: "UTC" });
}

export function formatList(items: string[], locale: Locale, type: Intl.ListFormatType = "conjunction"): string {
  return memo(`list|${locale}|${type}`, () => new Intl.ListFormat(intlLocale(locale), { style: "long", type })).format(items);
}

/** Display name for a language code (e.g. "ar" -> "Arabic" / "العربية"). */
export function languageName(code: string, locale: Locale): string {
  try {
    return new Intl.DisplayNames([intlLocale(locale)], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** Display name for an ISO 3166-1 region (e.g. "AE"). */
export function regionName(code: string, locale: Locale): string {
  try {
    return new Intl.DisplayNames([intlLocale(locale)], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** Short offset label for an IANA zone at a given instant, e.g. "GMT+4". */
export function timeZoneLabel(timeZone: string, locale: Locale, at: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat(intlLocale(locale), { timeZone, timeZoneName: "shortOffset" }).formatToParts(at);
    return parts.find((p) => p.type === "timeZoneName")?.value ?? timeZone;
  } catch {
    return timeZone;
  }
}
