/** IANA time-zone arithmetic without a library (Intl only). */

function offsetMs(timestamp: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(timestamp);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
  return asUtc - Math.floor(timestamp / 1000) * 1000;
}

/** Wall-clock date + time in `timeZone` -> UTC ISO instant (e.g. "2027-01-10","09:00","Asia/Dubai" -> "2027-01-10T05:00:00.000Z"). */
export function zonedToUtcIso(date: string, time: string, timeZone: string): string {
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const tm = /^(\d{2}):(\d{2})$/.exec(time);
  if (!dm || !tm) throw new RangeError("Expected YYYY-MM-DD and HH:MM");
  const wall = Date.UTC(Number(dm[1]), Number(dm[2]) - 1, Number(dm[3]), Number(tm[1]), Number(tm[2]));
  let guess = wall;
  for (let i = 0; i < 3; i++) {
    const next = wall - offsetMs(guess, timeZone);
    if (next === guess) break;
    guess = next;
  }
  return new Date(guess).toISOString();
}

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/** "HH:MM" (or "24:00" as end) -> minutes, NaN if invalid. */
export function hhmmToMinutes(v: string, allowEndOfDay = false): number {
  if (allowEndOfDay && v === "24:00") return 1440;
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(v);
  return m ? Number(m[1]) * 60 + Number(m[2]) : Number.NaN;
}
