"use server";

import { NotFoundError, UnauthorizedError, unwrap, unwrapResponse, type Profile } from "@healuxa/api-client";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { act, invalid } from "@/lib/actions";
import { CONSENT_KEYS } from "@/lib/consent";
import { userApi } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { clearedTokenCookies } from "@/lib/auth/tokens";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

async function requireUser() {
  const session = await getSession();
  if (!session) throw new UnauthorizedError({ title: "Unauthorized", status: 401, code: "unauthorized" });
  return session;
}

export async function saveConsentAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    const session = await requireUser();
    const api = await userApi();
    let current: Profile | null = null;
    let etag: string | null = str(fd, "etag") || null;
    try {
      const res = await unwrapResponse(api.profile.GET("/profiles/{userId}", { params: { path: { userId: session.userId } } }));
      current = res.data;
      etag = etag ?? res.etag;
    } catch (error) {
      if (!(error instanceof NotFoundError)) throw error;
    }
    const now = new Date().toISOString();
    const previous = (current?.consent ?? {}) as Record<string, { granted?: boolean } | undefined>;
    const consent: Record<string, unknown> = { ...(current?.consent ?? {}) };
    for (const key of CONSENT_KEYS) {
      const granted = fd.get(key) === "on";
      // Record when each choice changed (audit trail lives in profile-service events).
      if (previous[key]?.granted !== granted) consent[key] = { granted, updated_at: now, source: "web", locale };
    }
    const body: Profile = {
      user_id: session.userId,
      ...(current?.lifecycle_stage ? { lifecycle_stage: current.lifecycle_stage } : {}),
      ...(current?.vip_tier ? { vip_tier: current.vip_tier } : {}),
      scores: current?.scores ?? {},
      consent,
    };
    await unwrap(
      api.profile.PUT("/profiles/{userId}", {
        params: { path: { userId: session.userId }, header: current && etag ? { "If-Match": etag } : {} },
        body,
      }),
    );
    revalidatePath(`/${locale}/account/profile`);
    return getT(locale)("account.consentSaved");
  }, (locale) => ({ conflict: getT(locale)("account.consentConflict") }));
}

export async function revokeSessionAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let signedOutLocale: string | null = null;
  const state = await act(fd, async (locale) => {
    const session = await requireUser();
    const id = str(fd, "session_id");
    const api = await userApi();
    await unwrap(api.identity.DELETE("/sessions/{id}", { params: { path: { id } } }));
    if (id === session.sessionId) {
      const store = await cookies();
      for (const c of clearedTokenCookies()) store.set(c);
      signedOutLocale = locale;
      return;
    }
    revalidatePath(`/${locale}/account/sessions`);
    return getT(locale)("account.sessionRevoked");
  });
  if (state.ok && signedOutLocale) redirect(`/${signedOutLocale}/login`);
  return state;
}

/** Permanent account deletion (identity-service re-checks the password and fans out auth.user_deleted). */
export async function deleteAccountAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let done = "";
  const state = await act(fd, async (locale) => {
    await requireUser();
    const t = getT(locale);
    const password = typeof fd.get("password") === "string" ? (fd.get("password") as string) : "";
    if (!password) return invalid(locale, { password: t("auth.passwordRequired") });
    if (str(fd, "confirm_text") !== "DELETE") return invalid(locale, { confirm_text: t("account.deleteConfirmError") });
    const api = await userApi();
    await unwrap(api.identity.POST("/auth/delete-account", { body: { password } }));
    const store = await cookies();
    for (const c of clearedTokenCookies()) store.set(c);
    done = locale;
  }, (locale) => ({ unauthorized: getT(locale)("account.deleteWrongPassword") }));
  if (state.ok && done) redirect(`/${done}?accountDeleted=1`);
  return state;
}
