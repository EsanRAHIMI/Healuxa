import { unwrap } from "@healuxa/api-client";
import { formatDate } from "@healuxa/i18n";
import { redirect } from "next/navigation";

import { submitCredentialAction } from "@/actions/provider";
import { StatusBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Alert, Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyProvider } from "@/lib/portal";

const KINDS = ["professional_license", "board_certification", "malpractice_insurance", "other"] as const;

export default async function CredentialsPage({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  const { provider } = mine;
  const applied = (await searchParams).applied === "1";
  const api = await userApi();
  const creds = await settle(() => unwrap(api.provider.GET("/providers/{id}/credentials", { params: { path: { id: provider.id } } })));
  const req = { required: true, requiredLabel: t("common.required") };
  const opt = { optionalLabel: t("common.optional") };
  return (
    <>
      <PageHeader title={t("pp.credentials")} lead={t("pp.credentialsLead")} />
      {applied ? <Alert tone="success" role="status" className="mb-6" title={t("pp.appliedTitle")}>{t("pp.appliedBody")}</Alert> : null}
      <Section title={t("pp.submittedCredentials")} id="list">
        {!creds.ok ? (
          <ServiceError error={creds.error} locale={locale} />
        ) : creds.value.data.length === 0 ? (
          <EmptyState title={t("pp.noCredentials")} body={t("pp.noCredentialsBody")} />
        ) : (
          <ul className="space-y-3" data-testid="credentials">
            {creds.value.data.map((c) => (
              <Card as="li" key={c.id} className="flex flex-wrap items-start justify-between gap-3" data-testid="credential">
                <div>
                  <p className="font-medium">{t(`enums.credentialKind.${c.kind}`)} · {c.issuing_authority}</p>
                  <p className="text-sm text-text-muted">
                    <span className="hx-ltr-nums">{c.number}</span>
                    {c.valid_until ? ` · ${t("profile.validUntil", { date: formatDate(c.valid_until, locale) })}` : ""}
                  </p>
                  {c.review_note ? <p className="mt-1 text-sm">{t("pp.reviewNote")}: <span lang="en">{c.review_note}</span></p> : null}
                </div>
                <StatusBadge status={c.status} kind="credentialStatus" locale={locale} />
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("pp.submitCredential")} description={t("pp.submitCredentialLead")} id="submit">
        <Card className="max-w-3xl">
          <Form action={submitCredentialAction} locale={locale} label={t("pp.submitCredential")} hidden={{ provider_id: provider.id }} resetOnSuccess testId="credential-form">
            <div className="grid gap-5 sm:grid-cols-2">
              <SelectField name="kind" label={t("pp.kind")} {...req} options={KINDS.map((k) => ({ value: k, label: t(`enums.credentialKind.${k}`) }))} />
              <TextField name="issuing_authority" label={t("pp.authority")} hint={t("pp.authorityHint")} {...req} maxLength={64} />
              <TextField name="number" label={t("pp.number")} {...req} maxLength={64} autoComplete="off" />
              <TextField name="jurisdiction" label={t("pp.jurisdiction")} hint={t("pp.jurisdictionHint")} {...opt} maxLength={16} />
              <TextField name="valid_from" type="date" label={t("pp.validFrom")} {...opt} />
              <TextField name="valid_until" type="date" label={t("pp.validUntil")} {...opt} />
            </div>
            <p className="mt-4 text-sm text-text-muted">{t("pp.documentNote")}</p>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("pp.submitting")}>{t("pp.submitCredential")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
