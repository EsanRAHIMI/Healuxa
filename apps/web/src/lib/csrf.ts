import "server-only";

import { cookies } from "next/headers";

import { cookieNames } from "@/lib/auth/tokens";

export const CSRF_FIELD = "_csrf";

/** Token rendered into every mutation form (set by src/proxy.ts on first visit). */
export async function getCsrfToken(): Promise<string> {
  return (await cookies()).get(cookieNames().csrf)?.value ?? "";
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export class CsrfError extends Error {
  constructor() {
    super("CSRF token missing or invalid");
    this.name = "CsrfError";
  }
}

/**
 * Double-submit check on top of Next's Origin/Host comparison (which lets Origin-less requests
 * through): the form field must equal the httpOnly SameSite cookie, which a cross-site page can
 * neither read nor set.
 */
export async function assertCsrf(formData: FormData): Promise<void> {
  const presented = formData.get(CSRF_FIELD);
  const expected = await getCsrfToken();
  if (typeof presented !== "string" || !expected || !timingSafeEqual(presented, expected)) throw new CsrfError();
}
