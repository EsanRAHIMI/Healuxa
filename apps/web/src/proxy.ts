import { DEFAULT_LOCALE, LAUNCH_LOCALES, LOCALES, isLocale, negotiateLocale, type Locale } from "@healuxa/i18n";
import { NextResponse, type NextRequest } from "next/server";

import {
  LOCALE_COOKIE,
  clearedTokenCookies,
  cookieNames,
  cookieSecure,
  needsRefresh,
  rotateRefreshToken,
  tokenCookies,
  type CookieSpec,
} from "@/lib/auth/tokens";
import { buildCsp, newCsrfToken, newNonce } from "@/lib/security";

const launch = LAUNCH_LOCALES as readonly Locale[];

function identityApiUrl(): string {
  return process.env.IDENTITY_API_URL || "http://127.0.0.1:8001/v1";
}

function isPrefetch(request: NextRequest): boolean {
  return request.headers.has("next-router-prefetch") || request.headers.get("purpose") === "prefetch";
}

function serializeCookieHeader(jar: Map<string, string>): string {
  return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const [, first = "", ...rest] = pathname.split("/");

  // 1. Locale prefix. Launch locales are served; scaffold locales (fr/de) fall back to English.
  if (!isLocale(first) || !launch.includes(first)) {
    const preferred = request.cookies.get(LOCALE_COOKIE)?.value;
    const locale: Locale =
      preferred && isLocale(preferred) && launch.includes(preferred)
        ? preferred
        : negotiateLocale(request.headers.get("accept-language"), launch, DEFAULT_LOCALE);
    const tail = isLocale(first) && (LOCALES as readonly string[]).includes(first) ? rest.join("/") : pathname.slice(1);
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}${tail ? `/${tail}` : ""}`;
    url.search = search;
    return NextResponse.redirect(url, 307);
  }

  const locale = first as Locale;
  const secure = cookieSecure();
  const names = cookieNames(secure);
  const jar = new Map(request.cookies.getAll().map((c) => [c.name, c.value] as const));
  const setCookies: CookieSpec[] = [];

  // 2. Silent session refresh before rendering, so Server Components always see a valid access token.
  const refreshToken = jar.get(names.refresh);
  if (refreshToken && needsRefresh(jar.get(names.access)) && !isPrefetch(request)) {
    const forwarded = request.headers.get("x-forwarded-for");
    const result = await rotateRefreshToken(identityApiUrl(), refreshToken, {
      headers: {
        ...(forwarded ? { "X-Forwarded-For": forwarded.split(",")[0]!.trim() } : {}),
        "User-Agent": (request.headers.get("user-agent") ?? "").slice(0, 256),
      },
    });
    if (result.ok) {
      for (const c of tokenCookies(result.tokens)) {
        setCookies.push(c);
        jar.set(c.name, c.value);
      }
    } else if (result.status === 401) {
      for (const c of clearedTokenCookies()) {
        setCookies.push(c);
        jar.delete(c.name);
      }
    }
  }

  // 3. CSRF double-submit token for Server Action forms (checked in src/lib/csrf.ts).
  if (!jar.get(names.csrf)) {
    const token = newCsrfToken();
    jar.set(names.csrf, token);
    setCookies.push({ name: names.csrf, value: token, httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 60 * 60 * 12 });
  }

  // Remember the chosen language for the next locale-less visit.
  if (jar.get(LOCALE_COOKIE) !== locale) {
    setCookies.push({ name: LOCALE_COOKIE, value: locale, httpOnly: false, secure, sameSite: "lax", path: "/", maxAge: 31536000 });
  }

  // 4. Per-request CSP nonce (Next applies it to its own scripts).
  const nonce = newNonce();
  const csp = buildCsp(nonce, {
    dev: process.env.NODE_ENV === "development",
    https: request.nextUrl.protocol === "https:" || request.headers.get("x-forwarded-proto") === "https",
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", csp);
  requestHeaders.set("x-hx-pathname", pathname);
  requestHeaders.set("x-hx-locale", locale);
  requestHeaders.set("cookie", serializeCookieHeader(jar));

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Vary", "Accept-Language, Cookie");
  for (const c of setCookies) response.cookies.set(c);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api/|_next/static|_next/image|favicon.ico|icon.svg|apple-icon.png|robots.txt|sitemap.xml|manifest.webmanifest|.*\\.[a-z0-9]{2,5}$).*)",
    },
  ],
};
