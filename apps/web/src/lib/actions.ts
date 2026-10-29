import "server-only";

import { HealuxaApiError, isApiError } from "@healuxa/api-client";
import { isLocale, type Locale } from "@healuxa/i18n";
import { unstable_rethrow } from "next/navigation";

import { CsrfError, assertCsrf } from "@/lib/csrf";
import type { FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

export function formLocale(fd: FormData): Locale {
  const v = fd.get("_locale");
  return typeof v === "string" && isLocale(v) ? v : "en";
}

/** Translate an API error into form state. Specific known conflicts get dedicated messages. */
export function errorState(error: unknown, locale: Locale, overrides: Partial<Record<string, string>> = {}): FormState {
  const t = getT(locale);
  if (error instanceof CsrfError) return { ok: false, message: t("errors.csrf"), at: Date.now() };
  if (isApiError(error)) {
    const e = error as HealuxaApiError;
    const fieldErrors: Record<string, string> = {};
    for (const fe of e.fieldErrors) fieldErrors[fe.field.split(".").pop() ?? fe.field] = fe.message ?? fe.code;
    return {
      ok: false,
      message: overrides[e.code] ?? t(`errors.${e.code}`),
      detail: e.detail,
      traceId: e.traceId,
      fieldErrors: Object.keys(fieldErrors).length ? fieldErrors : undefined,
      at: Date.now(),
    };
  }
  console.error("[action] unexpected error", error);
  return { ok: false, message: t("errors.internal_error"), at: Date.now() };
}

/**
 * Wrap a Server Action body: CSRF check, typed error mapping, redirect passthrough.
 * `run` returns a success message (or full state) — or calls redirect()/revalidatePath().
 */
export async function act(
  fd: FormData,
  run: (locale: Locale) => Promise<FormState | string | void>,
  overrides?: (locale: Locale) => Partial<Record<string, string>>,
): Promise<FormState> {
  const locale = formLocale(fd);
  try {
    await assertCsrf(fd);
    const result = await run(locale);
    if (typeof result === "string") return { ok: true, message: result, at: Date.now() };
    return result ?? { ok: true, at: Date.now() };
  } catch (error) {
    unstable_rethrow(error);
    return errorState(error, locale, overrides?.(locale));
  }
}

export function invalid(locale: Locale, fieldErrors: Record<string, string>): FormState {
  return { ok: false, message: getT(locale)("errors.validation_error"), fieldErrors, at: Date.now() };
}
