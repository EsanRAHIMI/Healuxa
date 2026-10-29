/** Read a single string search param (first value), trimmed and length-capped. */
export function qp(sp: Record<string, string | string[] | undefined>, name: string, max = 120): string | undefined {
  const raw = sp[name];
  const v = (Array.isArray(raw) ? raw[0] : raw)?.trim();
  return v ? v.slice(0, max) : undefined;
}

export function oneOf<T extends string>(value: string | undefined, allowed: readonly T[]): T | undefined {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : undefined;
}

/** Validate "lat,lng". */
export function parseNear(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const m = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/.exec(value);
  if (!m) return undefined;
  const lat = Number(m[1]);
  const lng = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? `${lat},${lng}` : undefined;
}

export const PROVIDER_TYPES = ["doctor", "clinic", "therapist", "trainer", "nutritionist", "pharmacy", "brand", "home_visit"] as const;
export const FACILITY_TYPES = ["clinic", "hospital", "medical_center", "day_surgery", "diagnostic_center", "pharmacy", "wellness_center"] as const;
/** Language filter choices (codes stored by provider-service, lowercase BCP 47). */
export const LANGUAGE_CODES = ["en", "ar", "fa", "fr", "de", "ru", "hi", "ur", "tl", "zh"] as const;
