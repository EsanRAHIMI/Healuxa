/** Shared Server Action state + FormData parsing (importable from client components: types only). */

export interface FormState {
  /** null = not submitted yet. */
  ok: boolean | null;
  message?: string;
  /** Raw server detail (English, from the API) shown as secondary text for support/debugging. */
  detail?: string;
  traceId?: string;
  fieldErrors?: Record<string, string>;
  /** Changes on every submission so status regions re-announce. */
  at?: number;
}

export const initialFormState: FormState = { ok: null };

export function str(fd: FormData, name: string): string {
  const v = fd.get(name);
  return typeof v === "string" ? v.trim() : "";
}

export function optStr(fd: FormData, name: string): string | undefined {
  const v = str(fd, name);
  return v === "" ? undefined : v;
}

export function optInt(fd: FormData, name: string): number | undefined {
  const v = str(fd, name);
  if (v === "") return undefined;
  const n = Number(v);
  return Number.isInteger(n) ? n : Number.NaN;
}

export function optNumber(fd: FormData, name: string): number | undefined {
  const v = str(fd, name);
  if (v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : Number.NaN;
}

/** Comma/newline separated list, trimmed, de-duplicated. */
export function list(fd: FormData, name: string): string[] {
  const raw = fd.getAll(name).flatMap((v) => (typeof v === "string" ? v.split(/[,\n]/) : []));
  return [...new Set(raw.map((s) => s.trim()).filter(Boolean))];
}

/**
 * "120.50" (major units, as typed) -> 12050 minor units. Returns NaN for invalid input.
 * Uses string arithmetic so 0.1 + 0.2 style float errors never reach a price.
 */
export function toMinorUnits(input: string, exponent = 2): number {
  const s = input.trim().replace(/[\s,]/g, "");
  if (s === "") return Number.NaN;
  const m = /^(\d+)(?:\.(\d+))?$/.exec(s);
  if (!m) return Number.NaN;
  const frac = m[2] ?? "";
  if (frac.length > exponent) return Number.NaN;
  return Number(m[1]) * 10 ** exponent + Number(frac.padEnd(exponent, "0") || "0");
}

export function fromMinorUnits(minor: number | null | undefined, exponent = 2): string {
  if (minor === null || minor === undefined) return "";
  const whole = Math.trunc(minor / 10 ** exponent);
  const frac = String(Math.abs(minor % 10 ** exponent)).padStart(exponent, "0");
  return exponent ? `${whole}.${frac}` : String(whole);
}
