import "server-only";

/**
 * Backend access for the web tier (BFF). The browser never calls services directly: Server
 * Components and Server Actions use these clients, one base URL per service (env.ts), forwarding the
 * user's access token from the httpOnly cookie. Public catalog reads are anonymous and cached.
 */

import { createHealuxaClient, type HealuxaClient } from "@healuxa/api-client";
import { cookies, headers } from "next/headers";
import { cache } from "react";

import { cookieNames, rotateRefreshToken, tokenCookies } from "@/lib/auth/tokens";
import { env } from "@/lib/env";

function baseUrls() {
  return {
    identity: env.identityApiUrl,
    provider: env.providerApiUrl,
    profile: env.profileApiUrl,
    assessment: env.assessmentApiUrl,
    appointment: env.appointmentApiUrl,
    concierge: env.conciergeApiUrl,
    notification: env.notificationApiUrl,
    payment: env.paymentApiUrl,
    subscription: env.subscriptionApiUrl,
  };
}

/** Headers forwarded to backends so identity-service records the real client IP for sessions/lockouts. */
export async function forwardedHeaders(): Promise<Record<string, string>> {
  const h = await headers();
  const out: Record<string, string> = {};
  if (env.trustForwardedFor) {
    const xff = h.get("x-forwarded-for") ?? h.get("x-real-ip");
    if (xff) out["X-Forwarded-For"] = xff.split(",")[0]!.trim();
  }
  const ua = h.get("user-agent");
  if (ua) out["User-Agent"] = ua.slice(0, 256);
  const trace = h.get("x-trace-id");
  if (trace) out["X-Trace-Id"] = trace;
  return out;
}

/**
 * Anonymous client for public directory/catalog reads. Responses go through the Next data cache
 * (revalidated every PUBLIC_REVALIDATE_SECONDS) so public pages stay fast while data stays fresh.
 */
export const publicApi = cache((): HealuxaClient =>
  createHealuxaClient({
    baseUrls: baseUrls(),
    timeoutMs: env.apiTimeoutMs,
    requestInitExt: { next: { revalidate: env.publicRevalidateSeconds, tags: ["public-catalog"] } },
  }),
);

/** Uncached anonymous client (auth endpoints, anything that must not be cached). */
export const anonymousApi = cache(async (): Promise<HealuxaClient> => {
  const fwd = await forwardedHeaders();
  return createHealuxaClient({
    baseUrls: baseUrls(),
    timeoutMs: env.apiTimeoutMs,
    headers: fwd,
    requestInitExt: { cache: "no-store" },
  });
});

/**
 * Client acting as the signed-in user. The access token comes from the httpOnly cookie; on a 401 it
 * rotates the refresh token once (shared with src/proxy.ts) and, inside Server Actions, persists the
 * new pair. Never cached.
 */
export const userApi = cache(async (): Promise<HealuxaClient> => {
  const store = await cookies();
  const names = cookieNames();
  const fwd = await forwardedHeaders();
  let accessToken = store.get(names.access)?.value ?? null;
  return createHealuxaClient({
    baseUrls: baseUrls(),
    timeoutMs: env.apiTimeoutMs,
    headers: fwd,
    requestInitExt: { cache: "no-store" },
    auth: {
      getAccessToken: () => accessToken,
      refresh: async () => {
        const refreshToken = store.get(names.refresh)?.value;
        if (!refreshToken) return null;
        // Rotating without persisting would strand the browser with a spent refresh token (and the next
        // use would trip identity-service's reuse detection). Server Components cannot set cookies, so
        // only rotate where we can write them (Server Actions / Route Handlers); src/proxy.ts covers pages.
        try {
          store.set({ name: "hx_probe", value: "", path: "/", maxAge: 0 });
        } catch {
          return null;
        }
        const result = await rotateRefreshToken(env.identityApiUrl, refreshToken, { headers: fwd, timeoutMs: env.apiTimeoutMs });
        if (!result.ok) return null;
        accessToken = result.tokens.access_token;
        for (const c of tokenCookies(result.tokens)) store.set(c);
        return accessToken;
      },
    },
  });
});
