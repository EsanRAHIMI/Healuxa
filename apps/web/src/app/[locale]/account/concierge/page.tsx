import { unwrap } from "@healuxa/api-client";
import { formatDate, languageName } from "@healuxa/i18n";
import Link from "next/link";

import { createCaseAction } from "@/actions/concierge";
import { StatusBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton, TextArea, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Alert, Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

const CATEGORIES = ["medical_travel", "specialist_search", "second_opinion_coordination", "logistics", "other"] as const;
const LANGS = ["en", "ar", "fa", "fr", "de", "ru"] as const;

export default async function MyConcierge({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const cases = await settle(() => unwrap(api.concierge.GET("/concierge/cases", { params: { query: { limit: 50 } } })));
  const opt = { optionalLabel: t("common.optional") };
  return (
    <>
      <PageHeader title={t("concierge.title")} lead={t("concierge.lead")} />
      <Section title={t("concierge.myCases")} id="cases">
        {!cases.ok ? (
          <ServiceError error={cases.error} locale={locale} />
        ) : cases.value.data.length === 0 ? (
          <EmptyState title={t("concierge.noCases")} />
        ) : (
          <ul className="space-y-3" data-testid="cases">
            {cases.value.data.map((c) => (
              <Card as="li" key={c.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <Link href={`/${locale}/account/concierge/${c.id}`} className="font-medium">
                    {t(`enums.caseCategory.${c.category}`)}
                  </Link>
                  <p className="text-sm text-text-muted">{formatDate(c.created_at, locale)}{c.destination_city ? ` · ${c.destination_city}` : ""}</p>
                </div>
                <StatusBadge status={c.status} kind="caseStatus" locale={locale} />
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("concierge.newCase")} description={t("concierge.newCaseLead")} id="new">
        <Card className="max-w-3xl">
          <Alert tone="warning" role="note" className="mb-5" title={t("concierge.noClinicalTitle")}>{t("concierge.noClinicalHint")}</Alert>
          <Form action={createCaseAction} locale={locale} label={t("concierge.newCase")} showSuccess={false} testId="case-form">
            <div className="grid gap-5 sm:grid-cols-2">
              <SelectField className="sm:col-span-2" name="category" label={t("concierge.category")} required requiredLabel={t("common.required")} options={CATEGORIES.map((c) => ({ value: c, label: t(`enums.caseCategory.${c}`) }))} />
              <TextField name="preferred_start_date" type="date" label={t("concierge.startDate")} {...opt} />
              <TextField name="preferred_end_date" type="date" label={t("concierge.endDate")} {...opt} />
              <TextField name="destination_city" label={t("concierge.city")} {...opt} maxLength={120} />
              <fieldset className="sm:col-span-2">
                <legend className="mb-1.5 text-sm font-medium">{t("concierge.languages")}</legend>
                <div className="flex flex-wrap gap-2">
                  {LANGS.map((l) => (
                    <label key={l} className="flex min-h-11 items-center gap-2 rounded-md border border-border px-3">
                      <input type="checkbox" name="languages" value={l} defaultChecked={l === locale} className="size-5 accent-[var(--hx-color-primary)]" />
                      {languageName(l, locale)}
                    </label>
                  ))}
                </div>
              </fieldset>
              <TextArea className="sm:col-span-2" name="needs_note" label={t("concierge.needs")} hint={t("concierge.needsHint")} {...opt} maxLength={2000} />
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("pp.submitting")}>{t("concierge.submit")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
