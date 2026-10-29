/**
 * Token cookie plumbing shared by the proxy (src/proxy.ts) and server code. No `server-only` import:
 * the proxy bundle loads this too. Never import from client components.
 */
import type { TokenResponse } from "@healuxa/api-client";

export const REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60;
/** Refresh this many seconds before the access token expires. */
export const REFRESH_SKEW_SECONDS = 60;

export function cookieSecure(): boolean {
  const raw = process.env.AUTH_COOKIE_SECURE;
  if (raw === undefined || raw === "") return process.env.NODE_ENV === "production";
  return ["1", "true", "yes", "on"].includes(raw.toLowerCase());
}

export interface CookieNames {
  access: string;
  refresh: string;
  csrf: string;
}

/** `__Host-` cookies are Secure, host-only and Path=/ — they cannot be planted by a sibling subdomain. */
export function cookieNames(secure = cookieSecure()): CookieNames {
  const p = secure ? "__Host-" : "";
  return { access: `${p}hx_at`, refresh: `${p}hx_rt`, csrf: `${p}hx_csrf` };
}

export const LOCALE_COOKIE = "hx_locale";
export const THEME_COOKIE = "hx_theme";
export const FACILITIES_COOKIE = "hx_facilities";

export interface CookieSpec {
  name: string;
  value: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax" | "strict";
  path: "/";
  maxAge: number;
}

export function tokenCookies(tokens: Pick<TokenResponse, "access_token" | "refresh_token" | "expires_in">): CookieSpec[] {
  const secure = cookieSecure();
  const names = cookieNames(secure);
  const out: CookieSpec[] = [
    { name: names.access, value: tokens.access_token, httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: tokens.expires_in },
  ];
  if (tokens.refresh_token) {
    out.push({ name: names.refresh, value: tokens.refresh_token, httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: REFRESH_TTL_SECONDS });
  }
  return out;
}

export function clearedTokenCookies(): CookieSpec[] {
  const secure = cookieSecure();
  const names = cookieNames(secure);
  return [names.access, names.refresh].map((name) => ({ name, value: "", httpOnly: true, secure, sameSite: "lax" as const, path: "/" as const, maxAge: 0 }));
}

function base64UrlDecode(input: string): string {
  const pad = input.length % 4 === 0 ? "" : "=".repeat(4 - (input.length % 4));
  const b64 = (input + pad).replace(/-/g, "+").replace(/_/g, "/");
  return typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("binary");
}

/** Unverified `exp` (seconds) — only used to decide WHEN to refresh; authorization always verifies. */
export function unverifiedExp(jwt: string | undefined | null): number | null {
  if (!jwt) return null;
  const part = jwt.split(".")[1];
  if (!part) return null;
  try {
    const payload = JSON.parse(base64UrlDecode(part)) as { exp?: unknown };
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

export function needsRefresh(accessToken: string | undefined | null, now = Date.now() / 1000): boolean {
  const exp = unverifiedExp(accessToken);
  return exp === null || exp - REFRESH_SKEW_SECONDS <= now;
}

type RefreshResult = { ok: true; tokens: TokenResponse } | { ok: false; status: number };

interface RefreshEntry {
  promise: Promise<RefreshResult>;
  settledAt: number | null;
}

/** Results are remembered briefly so parallel requests carrying the same (old) refresh token reuse them. */
const MEMO_MS = 30_000;
const registry: Map<string, RefreshEntry> = ((globalThis as Record<string, unknown>).__hxRefreshRegistry ??= new Map()) as Map<
  string,
  RefreshEntry
>;

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Rotate a refresh token exactly once per process even under concurrent requests. identity-service
 * treats a second use of the same refresh token as theft and revokes every session of the user.
 */
export async function rotateRefreshToken(
  identityApiUrl: string,
  refreshToken: string,
  init: { headers?: Record<string, string>; timeoutMs?: number } = {},
): Promise<RefreshResult> {
  const key = await sha256(refreshToken);
  const now = Date.now();
  for (const [k, entry] of registry) {
    if (entry.settledAt !== null && now - entry.settledAt > MEMO_MS) registry.delete(k);
  }
  const existing = registry.get(key);
  if (existing) return existing.promise;

  const entry: RefreshEntry = { settledAt: null, promise: Promise.resolve({ ok: false, status: 0 }) };
  entry.promise = (async (): Promise<RefreshResult> => {
    try {
      const response = await fetch(`${identityApiUrl.replace(/\/+$/, "")}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json", ...init.headers },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
        signal: AbortSignal.timeout(init.timeoutMs ?? 8000),
      });
      if (!response.ok) return { ok: false, status: response.status };
      return { ok: true, tokens: (await response.json()) as TokenResponse };
    } catch {
      return { ok: false, status: 0 };
    } finally {
      entry.settledAt = Date.now();
    }
  })();
  registry.set(key, entry);
  return entry.promise;
}

/** Test helper. */
export function _resetRefreshRegistry(): void {
  registry.clear();
}
