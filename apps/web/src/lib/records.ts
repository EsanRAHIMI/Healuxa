import "server-only";

import { unwrap, type Appointment, type MedicalRecordList, type RecordAccessLogEntry, type RecordGrant } from "@healuxa/api-client";
import { cookies, headers } from "next/headers";

import { userApi } from "@/lib/api";
import { cookieNames } from "@/lib/auth/tokens";
import { getPublicFacility, getPublicProvider } from "@/lib/catalog";
import { env } from "@/lib/env";

/** Upload limit applied by the web tier before anything reaches profile-service (which enforces its own). */
export const MAX_UPLOAD_BYTES = Number(process.env.RECORDS_MAX_UPLOAD_BYTES || 10 * 1024 * 1024);
/** Multipart framing and text fields on top of the file. */
export const FORM_OVERHEAD_BYTES = 64 * 1024;
export const EXPIRY_CHOICES = [7, 30, 90, 180] as const;
export const DEFAULT_EXPIRY_DAYS = 30;
export const RECORD_TYPES = ["lab_result", "imaging_report", "prescription", "referral_letter", "discharge_summary", "other"] as const;
export const PURPOSES = ["consultation", "treatment", "second_opinion", "follow_up", "other"] as const;

export const ID_RE = /^[A-Za-z0-9-]{10,36}$/;

export interface Grantee {
  type: "provider" | "facility";
  id: string;
  name: string;
}

export async function listMyRecords(): Promise<MedicalRecordList> {
  const api = await userApi();
  return unwrap(api.profile.GET("/records"));
}

export async function listMyGrants(): Promise<RecordGrant[]> {
  const api = await userApi();
  return (await unwrap(api.profile.GET("/record-grants"))).data;
}

export async function recentAccess(limit = 100): Promise<RecordAccessLogEntry[]> {
  const api = await userApi();
  return (await unwrap(api.profile.GET("/record-access-log", { params: { query: { limit } } }))).data;
}

/** Providers and facilities from the customer's own bookings, named from the public directory. */
export async function careTeam(userId: string, appointments?: Appointment[]): Promise<Grantee[]> {
  let list = appointments;
  if (!list) {
    const api = await userApi();
    list = (await unwrap(api.appointment.GET("/appointments", { params: { query: { user_id: userId, sort: "-scheduled_at", limit: 50 } } }))).data;
  }
  const relevant = list.filter((a) => !["held", "expired", "declined"].includes(a.status));
  const providerIds = [...new Set(relevant.map((a) => a.provider_id))];
  const facilityIds = [...new Set(relevant.map((a) => a.facility_id))];
  const [providers, facilities] = await Promise.all([
    Promise.all(providerIds.map((id) => getPublicProvider(id).catch(() => null))),
    Promise.all(facilityIds.map((id) => getPublicFacility(id).catch(() => null))),
  ]);
  return [
    ...providers.filter((p) => !!p).map((p) => ({ type: "provider" as const, id: p!.id, name: p!.display_name })),
    ...facilities.filter((f) => !!f).map((f) => ({ type: "facility" as const, id: f!.id, name: f!.name })),
  ];
}

export function formatBytes(bytes: number, locale: string): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: unit ? 1 : 0 }).format(value)} ${units[unit]}`;
}

/**
 * Route-handler guard for the records endpoints: the request must come from this site (Fetch Metadata
 * or Origin) and, for writes, carry the CSRF token that matches the httpOnly cookie (double submit).
 */
export async function guardRequest(request: Request, { write }: { write: boolean }): Promise<{ token: string } | Response> {
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin" && !(site === "none" && !write)) return new Response("Forbidden", { status: 403 });
  const origin = request.headers.get("origin");
  if (write && origin) {
    const h = await headers();
    const host = h.get("x-forwarded-host") ?? h.get("host");
    try {
      if (!host || new URL(origin).host !== host) return new Response("Forbidden", { status: 403 });
    } catch {
      return new Response("Forbidden", { status: 403 });
    }
  }
  const store = await cookies();
  const names = cookieNames();
  if (write) {
    const presented = request.headers.get("x-csrf-token") ?? "";
    const expected = store.get(names.csrf)?.value ?? "";
    if (!expected || presented.length !== expected.length || !timingSafeEqual(presented, expected)) {
      return Response.json({ code: "csrf" }, { status: 403 });
    }
  }
  const token = store.get(names.access)?.value;
  if (!token) return Response.json({ code: "unauthorized" }, { status: 401 });
  return { token };
}

function timingSafeEqual(a: string, b: string): boolean {
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function forwardHeaders(): Promise<Record<string, string>> {
  const h = await headers();
  const out: Record<string, string> = {};
  if (env.trustForwardedFor) {
    const xff = h.get("x-forwarded-for") ?? h.get("x-real-ip");
    if (xff) out["X-Forwarded-For"] = xff.split(",")[0]!.trim();
  }
  const ua = h.get("user-agent");
  if (ua) out["User-Agent"] = ua.slice(0, 256);
  return out;
}
