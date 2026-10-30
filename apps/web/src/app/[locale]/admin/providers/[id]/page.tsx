import { NotFoundError, unwrap } from "@healuxa/api-client";
import { formatDate, formatList, languageName } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { changeProviderStatusAction, reviewCredentialAction } from "@/actions/admin";
import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { SelectField, SubmitButton, TextArea } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { DecisionForm } from "@/components/portal/DecisionForm";
import { Card, DefinitionList, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";

/** Staff view of one provider: credentials (with review) and lifecycle status change with reason. */
export default async function AdminProvider({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  const api = await userApi();
  const provider = await unwrap(api.provider.GET("/providers/{id}", { params: { path: { id } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const credentials = await unwrap(api.provider.GET("/providers/{id}/credentials", { params: { path: { id } } })).then((r) => r.data).catch(() => []);
  const next: Record<string, string[]> = { pending: ["active", "offboarded"], active: ["suspended", "offboarded"], suspended: ["active", "offboarded"], offboarded: [] };
  const options = next[provider.status] ?? [];
  return (
    <>
      <PageHeader
        title={provider.display_name}
        lead={provider.title ?? undefined}
        actions={
          <div className="flex gap-2">
            <VerificationBadge status={provider.verification_status} locale={locale} />
            <span data-testid="admin-provider-status">
              <StatusBadge status={provider.status} kind="providerStatus" locale={locale} />
            </span>
          </div>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-8">
          <Card>
            <DefinitionList
              items={[
                { term: t("pp.type"), value: t(`enums.providerType.${provider.type}`) },
                { term: t("providers.specialties"), value: provider.specialties.join(", ") },
                { term: t("providers.languages"), value: formatList(provider.languages.map((l) => languageName(l, locale)), locale) },
                { term: t("admin.ownerAccount"), value: <span className="hx-ltr-nums text-sm">{provider.user_id ?? "—"}</span> },
                { term: t("common.id"), value: <span className="hx-ltr-nums text-sm">{provider.id}</span> },
              ]}
            />
            {provider.status === "active" ? (
              <p className="mt-4">
                <Link href={`/${locale}/providers/${provider.id}`}>{t("pp.viewPublic")}</Link>
              </p>
            ) : null}
          </Card>
          <Section title={t("pp.credentials")} id="credentials">
            <ul className="space-y-3">
              {credentials.map((c) => (
                <Card as="li" key={c.id} className="space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{t(`enums.credentialKind.${c.kind}`)} · {c.issuing_authority}</p>
                      <p className="text-sm text-text-muted">
                        <span className="hx-ltr-nums">{c.number}</span>
                        {c.valid_until ? ` · ${t("profile.validUntil", { date: formatDate(c.valid_until, locale) })}` : ""}
                      </p>
                      {c.review_note ? <p className="text-sm">{t("pp.reviewNote")}: {c.review_note}</p> : null}
                    </div>
                    <StatusBadge status={c.status} kind="credentialStatus" locale={locale} />
                  </div>
                  {c.status === "submitted" ? <DecisionForm action={reviewCredentialAction} locale={locale} hidden={{ provider_id: provider.id, credential_id: c.id }} /> : null}
                </Card>
              ))}
            </ul>
          </Section>
        </div>
        <Card className="h-fit">
          <h2 className="text-lg">{t("admin.changeStatus")}</h2>
          {options.length === 0 ? (
            <p className="mt-2 text-text-muted">{t("admin.noTransitions")}</p>
          ) : (
            <Form action={changeProviderStatusAction} locale={locale} hidden={{ provider_id: provider.id }} label={t("admin.changeStatus")} testId="status-form">
              <div className="mt-3 space-y-4">
                <SelectField name="status" label={t("admin.newStatus")} required requiredLabel={t("common.required")} options={options.map((s) => ({ value: s, label: t(`enums.providerStatus.${s}`) }))} />
                <TextArea name="reason" label={t("admin.reason")} hint={t("admin.reasonHint")} required requiredLabel={t("common.required")} maxLength={1000} rows={3} />
                <SubmitButton pendingLabel={t("common.saving")} testId="status-submit">
                  {t("admin.applyStatus")}
                </SubmitButton>
              </div>
            </Form>
          )}
          {provider.verification_status !== "verified" && options.includes("active") ? <p className="mt-3 text-sm text-text-muted">{t("admin.activationRule")}</p> : null}
        </Card>
      </div>
    </>
  );
}
