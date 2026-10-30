import "server-only";

import { cookies } from "next/headers";

import { FACILITIES_COOKIE, cookieSecure } from "@/lib/auth/tokens";

const ID = /^[A-Za-z0-9-]{10,36}$/;

/**
 * provider-service has no "facilities I administer" endpoint yet, so this browser remembers the
 * facilities the user registered/opened. Ids only (no PII); every page re-checks access via the API.
 */
export async function rememberedFacilities(): Promise<string[]> {
  const raw = (await cookies()).get(FACILITIES_COOKIE)?.value ?? "";
  return raw.split(".").filter((id) => ID.test(id)).slice(0, 20);
}

export async function rememberFacility(id: string): Promise<void> {
  if (!ID.test(id)) return;
  const current = await rememberedFacilities();
  const next = [id, ...current.filter((x) => x !== id)].slice(0, 20);
  (await cookies()).set({ name: FACILITIES_COOKIE, value: next.join("."), httpOnly: true, secure: cookieSecure(), sameSite: "lax", path: "/", maxAge: 31536000 });
}

export async function forgetFacility(id: string): Promise<void> {
  const next = (await rememberedFacilities()).filter((x) => x !== id);
  (await cookies()).set({ name: FACILITIES_COOKIE, value: next.join("."), httpOnly: true, secure: cookieSecure(), sameSite: "lax", path: "/", maxAge: 31536000 });
}
