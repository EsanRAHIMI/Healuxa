import "server-only";

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { env } from "@/lib/env";
import type { Locale } from "@healuxa/i18n";

import { cookieNames } from "./tokens";

export interface Session {
  userId: string;
  tenant: string;
  roles: string[];
  permissions: string[];
  sessionId: string | null;
  accessToken: string;
  expiresAt: number;
}

type JwksFn = ReturnType<typeof createRemoteJWKSet>;
const globalJwks = globalThis as unknown as { __hxJwks?: { url: string; fn: JwksFn } };

function jwks(): JwksFn {
  const url = env.identityJwksUrl;
  if (!globalJwks.__hxJwks || globalJwks.__hxJwks.url !== url) {
    globalJwks.__hxJwks = { url, fn: createRemoteJWKSet(new URL(url), { cooldownDuration: 30_000, cacheMaxAge: 10 * 60_000 }) };
  }
  return globalJwks.__hxJwks.fn;
}

interface AccessClaims extends JWTPayload {
  tenant?: string;
  roles?: string[];
  perms?: string[];
  session_id?: string;
  typ?: string;
}

/** Verify an identity-service access token (RS256, JWKS, issuer, exp). Returns null if invalid. */
export async function verifyAccessToken(token: string): Promise<Session | null> {
  try {
    const { payload } = await jwtVerify<AccessClaims>(token, jwks(), {
      issuer: env.jwtIssuer,
      algorithms: ["RS256"],
      requiredClaims: ["sub", "exp"],
    });
    if (payload.typ && payload.typ !== "user") return null;
    return {
      userId: payload.sub!,
      tenant: payload.tenant ?? "healuxa-dubai",
      roles: Array.isArray(payload.roles) ? payload.roles : [],
      permissions: Array.isArray(payload.perms) ? payload.perms : [],
      sessionId: payload.session_id ?? null,
      accessToken: token,
      expiresAt: payload.exp!,
    };
  } catch {
    return null;
  }
}

/** The signed-in user for this request, or null. Memoised per request. */
export const getSession = cache(async (): Promise<Session | null> => {
  const store = await cookies();
  const token = store.get(cookieNames().access)?.value;
  if (!token) return null;
  return verifyAccessToken(token);
});

export function hasPermission(session: Session | null, permission: string): boolean {
  return !!session && session.permissions.includes(permission);
}

async function currentPath(locale: Locale): Promise<string> {
  const h = await headers();
  const path = h.get("x-hx-pathname");
  return path && path.startsWith(`/${locale}`) ? path : `/${locale}`;
}

/** Redirect to login (returning here afterwards) when signed out. */
export async function requireSession(locale: Locale): Promise<Session> {
  const session = await getSession();
  if (!session) {
    const next = await currentPath(locale);
    redirect(`/${locale}/login?next=${encodeURIComponent(next)}`);
  }
  return session;
}

/** Only allow same-site relative redirect targets inside a locale. */
export function safeNext(next: string | null | undefined, locale: Locale, fallback: string): string {
  if (!next) return fallback;
  if (!next.startsWith(`/${locale}/`) && next !== `/${locale}`) return fallback;
  if (next.startsWith("//") || next.includes("\\") || /[\u0000-\u001f]/.test(next)) return fallback;
  return next;
}
