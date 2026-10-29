import type { Locale } from "@healuxa/i18n";
import type { ReactNode } from "react";

import { getCsrfToken } from "@/lib/csrf";
import type { FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

import { ActionForm } from "./ActionForm";

/** Server wrapper: injects the CSRF token and translated status labels into an ActionForm. */
export async function Form({
  action,
  locale,
  children,
  className,
  label,
  showSuccess,
  resetOnSuccess,
  hidden,
  testId,
}: {
  action: (prev: FormState, fd: FormData) => Promise<FormState>;
  locale: Locale;
  children: ReactNode;
  className?: string;
  label?: string;
  showSuccess?: boolean;
  resetOnSuccess?: boolean;
  hidden?: Record<string, string>;
  testId?: string;
}) {
  const csrf = await getCsrfToken();
  const t = getT(locale);
  return (
    <ActionForm
      action={action}
      csrf={csrf}
      locale={locale}
      className={className}
      label={label}
      showSuccess={showSuccess}
      resetOnSuccess={resetOnSuccess}
      hidden={hidden}
      testId={testId}
      detailLabel={t("errors.detailLabel")}
      referenceLabel={t("errors.referenceLabel")}
    >
      {children}
    </ActionForm>
  );
}
