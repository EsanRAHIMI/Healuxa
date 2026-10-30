import type { Locale } from "@healuxa/i18n";

import { SubmitButton, TextArea } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import type { FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

/** Approve / reject with a mandatory reviewer note (kept in the service's audit fields). */
export function DecisionForm({ action, locale, hidden, testId }: { action: (prev: FormState, fd: FormData) => Promise<FormState>; locale: Locale; hidden: Record<string, string>; testId?: string }) {
  const t = getT(locale);
  return (
    <Form action={action} locale={locale} hidden={hidden} label={t("admin.decision")} testId={testId}>
      <TextArea name="note" label={t("admin.note")} hint={t("admin.noteHint")} required requiredLabel={t("common.required")} maxLength={1000} rows={2} />
      <div className="mt-3 flex flex-wrap gap-2">
        <SubmitButton name="decision" value="verify" pendingLabel={t("common.saving")} testId={testId ? `${testId}-verify` : undefined}>
          {t("admin.verify")}
        </SubmitButton>
        <SubmitButton name="decision" value="reject" variant="danger" pendingLabel={t("common.saving")}>
          {t("admin.reject")}
        </SubmitButton>
      </div>
    </Form>
  );
}
