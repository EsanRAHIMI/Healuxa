import { unwrap } from "@healuxa/api-client";
import { redirect } from "next/navigation";

import { requestAffiliationAction } from "@/actions/provider";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { AffiliationList } from "@/components/portal/AffiliationList";
import { Alert, Card, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { listPublicBranches, searchFacilities } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { branchLabels, getMyProvider } from "@/lib/portal";

export default async function ProviderAffiliations({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  const { provider } = mine;
  const api = await userApi();
  const affs = await settle(() => unwrap(api.provider.GET("/providers/{id}/affiliations", { params: { path: { id: provider.id } } })));
  const labels = affs.ok ? await branchLabels(affs.value.data.map((a) => a.facility_id)) : new Map();
  // Branch picker: open branches of verified facilities (public directory).
  const choices = await settle(async () => {
    const facilities = (await searchFacilities({ limit: 50 })).data;
    const rows = await Promise.all(facilities.map(async (f) => (await listPublicBranches(f.id)).filter((b) => b.status !== "closed").map((b) => ({ value: b.id, label: `${f.name} — ${b.name} (${b.city})` }))));
    return rows.flat();
  });
  return (
    <>
      <PageHeader title={t("pp.affiliations")} lead={t("pp.affiliationsLead")} />
      {provider.verification_status !== "verified" ? <Alert tone="info" role="note" className="mb-6" title={t("pp.affiliationNeedsVerification")} /> : null}
      <Section title={t("pp.yourAffiliations")} id="list">
        {!affs.ok ? (
          <ServiceError error={affs.error} locale={locale} />
        ) : (
          <AffiliationList
            affiliations={affs.value.data}
            side="provider"
            locale={locale}
            labelFor={(a) => {
              const l = labels.get(a.branch_id);
              return l ? { title: l.facility, subtitle: `${l.branch.name}, ${l.branch.city}` } : { title: a.facility_id, subtitle: a.branch_id };
            }}
          />
        )}
      </Section>
      <Section title={t("pp.requestAffiliation")} description={t("pp.requestAffiliationLead")} id="request">
        <Card className="max-w-3xl">
          <Form action={requestAffiliationAction} locale={locale} label={t("pp.requestAffiliation")} hidden={{ provider_id: provider.id }} testId="affiliation-form">
            {choices.ok && choices.value.length > 0 ? (
              <SelectField name="branch_id" label={t("pp.branch")} required requiredLabel={t("common.required")} placeholder={t("pp.chooseBranch")} options={choices.value} />
            ) : (
              <TextField name="branch_id" label={t("pp.branchId")} hint={t("pp.branchIdHint")} required requiredLabel={t("common.required")} />
            )}
            <div className="mt-6">
              <SubmitButton pendingLabel={t("pp.submitting")}>{t("pp.sendRequest")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
