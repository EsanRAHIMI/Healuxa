/**
 * Date/time display. Appointment times are always shown in the BRANCH time zone returned by
 * appointment-service (never the device zone), so a traveller sees the clinic's local time.
 */
const TAG: Record<string, string> = { en: 'en-AE', ar: 'ar-AE', fa: 'fa-IR' };

function fmt(iso: string, language: string, opts: Intl.DateTimeFormatOptions, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  try {
    return new Intl.DateTimeFormat(TAG[language] ?? language, { ...opts, timeZone }).format(d);
  } catch {
    // Engine without time-zone data: fall back to the branch-local wall clock in the ISO string.
    return iso.replace('T', ' ').slice(0, 16);
  }
}

export const formatDayHeading = (iso: string, language: string, timeZone?: string) =>
  fmt(iso, language, { weekday: 'long', day: 'numeric', month: 'long' }, timeZone);

export const formatTime = (iso: string, language: string, timeZone?: string) =>
  fmt(iso, language, { hour: '2-digit', minute: '2-digit' }, timeZone);

export const formatDateTime = (iso: string, language: string, timeZone?: string) =>
  fmt(iso, language, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }, timeZone);

/** Branch-local calendar date (YYYY-MM-DD) of a `local_start` string such as 2026-11-02T09:00:00+04:00. */
export const localDate = (localIso: string) => localIso.slice(0, 10);

/** YYYY-MM-DD for `days` from now in the given time zone (used for listAvailableSlots from/to). */
export function isoDateInZone(days: number, timeZone: string, now = new Date()): string {
  const d = new Date(now.getTime() + days * 86_400_000);
  try {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
    if (/^\d{4}-\d{2}-\d{2}$/.test(parts)) return parts;
  } catch {
    /* fall through */
  }
  return d.toISOString().slice(0, 10);
}
