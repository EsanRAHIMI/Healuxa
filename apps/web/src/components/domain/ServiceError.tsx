import { isApiError } from "@healuxa/api-client";
import type { Locale } from "@healuxa/i18n";

import { Alert } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

/** Inline, non-fatal error for a data region that failed to load (the rest of the page still works). */
export function ServiceError({ error, locale }: { error: unknown; locale: Locale }) {
  const t = getT(locale);
  const code = isApiError(error) ? error.code : "internal_error";
  if (!isApiError(error)) console.error("[page] data load failed", error);
  return (
    <Alert tone="warning" role="alert" title={t("errors.loadFailed")}>
      <p>{t(`errors.${code}`)}</p>
      {isApiError(error) && error.traceId ? (
        <p className="mt-1 text-xs">
          {t("errors.referenceLabel")}: <span className="hx-ltr-nums">{error.traceId}</span>
        </p>
      ) : null}
    </Alert>
  );
}

/** Render `fn` result or a ServiceError. */
export async function settle<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: unknown }> {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error };
  }
}
