import { newIdempotencyKey } from "@healuxa/api-client";
import { languageName } from "@healuxa/i18n";
import type { Metadata } from "next";

import { submitIntakeAction } from "@/actions/journey";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton, TextArea } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { ButtonLink, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { INTAKE_NOTES_MAX, INTAKE_QUESTIONS } from "@/lib/journey";
import { loadJourney } from "@/lib/journey-server";
import { privateMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("journey.intake.title"));
}

/** Intake preferences: coordination details only (timing, place, language, preferences). */
export default async function IntakePage({ params }: Props) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const res = await settle(() => loadJourney(session.userId));
  const back = <ButtonLink href={`/${locale}/journey`}>{t("journey.title")}</ButtonLink>;
  const intake = res.ok ? res.value?.phases.flatMap((p) => p.milestones).find((s) => s.code === "intake_assessment") : undefined;
  return (
    <div className="hx-container py-12">
      <PageHeader eyebrow={t("journey.title")} title={t("journey.intake.title")} lead={t("journey.intake.lead")} />
      {!res.ok ? (
        <ServiceError error={res.error} locale={locale} />
      ) : !res.value ? (
        <EmptyState title={t("journey.intake.noJourney")} action={back} />
      ) : intake?.status === "completed" ? (
        <EmptyState title={t("journey.intake.alreadyDone")} action={back} />
      ) : (
        <Card className="max-w-2xl">
          <Form action={submitIntakeAction} locale={locale} label={t("journey.intake.title")} showSuccess={false} hidden={{ idempotency_key: newIdempotencyKey("intake") }} testId="intake-form">
            <div className="space-y-5">
              {INTAKE_QUESTIONS.map((q) => (
                <SelectField
                  key={q.code}
                  name={q.code}
                  label={t(`journey.intake.${q.code}`)}
                  required
                  requiredLabel={t("common.required")}
                  placeholder={t("journey.intake.choose")}
                  defaultValue={q.code === "language" ? locale : ""}
                  options={q.options.map((o) => ({ value: o, label: q.code === "language" ? languageName(o, locale) : t(`journey.intake.${q.code}_${o}`) }))}
                />
              ))}
              <TextArea name="notes" label={t("journey.intake.notes")} hint={t("journey.intake.notesHint")} optionalLabel={t("common.optional")} maxLength={INTAKE_NOTES_MAX} rows={4} />
              <p className="text-sm text-text-muted">{t("journey.coordinationNote")}</p>
              <SubmitButton pendingLabel={t("journey.intake.saving")} testId="intake-submit">
                {t("journey.intake.submit")}
              </SubmitButton>
            </div>
          </Form>
        </Card>
      )}
    </div>
  );
}
