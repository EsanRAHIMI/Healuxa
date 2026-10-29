"use server";

import { idempotencyHeader, isApiError, unwrap } from "@healuxa/api-client";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { act, invalid } from "@/lib/actions";
import { anonymousApi, forwardedHeaders } from "@/lib/api";
import { safeNext } from "@/lib/auth/session";
import { THEME_COOKIE, clearedTokenCookies, cookieNames, tokenCookies } from "@/lib/auth/tokens";
import { env } from "@/lib/env";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

const IDENTIFIER = /^(?:[^\s@]+@[^\s@]+\.[^\s@]+|\+?[0-9 ()-]{7,20})$/;

async function persist(tokens: { access_token: string; refresh_token?: string; expires_in: number }) {
  const store = await cookies();
  for (const c of tokenCookies(tokens)) store.set(c);
}

export async function loginAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(
    fd,
    async (locale) => {
      const t = getT(locale);
      const identifier = str(fd, "identifier");
      const password = typeof fd.get("password") === "string" ? (fd.get("password") as string) : "";
      const errors: Record<string, string> = {};
      if (!identifier) errors.identifier = t("auth.identifierRequired");
      if (!password) errors.password = t("auth.passwordRequired");
      if (Object.keys(errors).length) return invalid(locale, errors);
      const api = await anonymousApi();
      const tokens = await unwrap(api.identity.POST("/auth/login", { body: { identifier, password } }));
      await persist(tokens);
      target = safeNext(str(fd, "next"), locale, `/${locale}/account`);
    },
    (locale) => ({ unauthorized: getT(locale)("auth.invalidCredentials") }),
  );
  if (state.ok && target) redirect(target);
  return state;
}

export async function registerAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(
    fd,
    async (locale) => {
      const t = getT(locale);
      const identifier = str(fd, "identifier");
      const password = typeof fd.get("password") === "string" ? (fd.get("password") as string) : "";
      const errors: Record<string, string> = {};
      if (!IDENTIFIER.test(identifier)) errors.identifier = t("auth.identifierInvalid");
      if (password.length < 8) errors.password = t("auth.passwordHint");
      if (fd.get("terms") !== "on") errors.terms = t("auth.termsRequired");
      if (Object.keys(errors).length) return invalid(locale, errors);
      // One key per submission attempt, carried in the form so a double-submit replays instead of duplicating.
      const key = str(fd, "idempotency_key");
      const api = await anonymousApi();
      const tokens = await unwrap(
        api.identity.POST("/auth/register", {
          params: { header: idempotencyHeader(key || undefined) },
          body: { identifier, password, locale: locale === "en" || locale === "ar" || locale === "fa" ? locale : undefined },
        }),
      );
      await persist(tokens);
      target = safeNext(str(fd, "next"), locale, `/${locale}/account`);
    },
    (locale) => ({ conflict: getT(locale)("auth.alreadyRegistered") }),
  );
  if (state.ok && target) redirect(target);
  return state;
}

export async function logoutAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let locale = "en";
  const state = await act(fd, async (l) => {
    locale = l;
    const store = await cookies();
    const token = store.get(cookieNames().access)?.value;
    if (token) {
      // Revoke server-side; a failure (already expired/revoked) must not keep the user signed in locally.
      try {
        const res = await fetch(`${env.identityApiUrl}/auth/logout`, {
          method: "POST",
          headers: { authorization: `Bearer ${token}`, ...(await forwardedHeaders()) },
          cache: "no-store",
          signal: AbortSignal.timeout(env.apiTimeoutMs),
        });
        if (!res.ok && res.status !== 401) console.warn("[logout] identity responded", res.status);
      } catch (error) {
        if (!isApiError(error)) console.warn("[logout] identity unreachable");
      }
    }
    for (const c of clearedTokenCookies()) store.set(c);
  });
  if (state.ok) redirect(`/${locale}?signedOut=1`);
  return state;
}

export async function setThemeAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async () => {
    const theme = str(fd, "theme");
    const store = await cookies();
    if (theme === "light" || theme === "dark") store.set({ name: THEME_COOKIE, value: theme, path: "/", maxAge: 31536000, sameSite: "lax", httpOnly: false });
    else store.delete(THEME_COOKIE);
    return { ok: true, at: Date.now() };
  });
}
