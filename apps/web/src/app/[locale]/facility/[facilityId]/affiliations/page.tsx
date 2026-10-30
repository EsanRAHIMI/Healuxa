import { unwrap, type Provider } from "@healuxa/api-client";

import { inviteProviderAction } from "@/actions/facility";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { AffiliationList } from "@/components/portal/AffiliationList";
import { Card, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { getBranchesAs } from "@/lib/portal";

export default async function FacilityAffiliations({ params }: { params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  const t = getT(locale);
  const api = await userApi();
  const data = await settle(async () => {
    const [affs, branches] = await Promise.all([
      unwrap(api.provider.GET("/facilities/{facility_id}/affiliations", { params: { path: { facility_id: facilityId } } })),
      getBranchesAs(facilityId),
    ]);
    const providers = new Map<string, Provider>();
    await Promise.all(
      [...new Set(affs.data.map((a) => a.provider_id))].map(async (id) => {
        const p = await unwrap(api.provider.GET("/providers/{id}", { params: { path: { id } } })).catch(() => null);
        if (p) providers.set(id, p);
      }),
    );
    return { affs: affs.data, branches, providers };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const { affs, branches, providers } = data.value;
  const branchMap = new Map(branches.map((b) => [b.id, b]));
  return (
    <>
      <Section title={t("pp.affiliations")} description={t("fp.affiliationsLead")} id="list">
        <AffiliationList
          affiliations={affs}
          side="facility"
          locale={locale}
          labelFor={(a) => ({
            title: providers.get(a.provider_id)?.display_name ?? a.provider_id,
            subtitle: branchMap.get(a.branch_id)?.name ?? a.branch_id,
          })}
        />
      </Section>
      <Section title={t("fp.inviteProvider")} description={t("fp.inviteProviderLead")} id="invite">
        <Card className="max-w-3xl">
          <Form action={inviteProviderAction} locale={locale} label={t("fp.inviteProvider")} resetOnSuccess>
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField name="provider_id" label={t("fp.providerId")} hint={t("fp.providerIdHint")} required requiredLabel={t("common.required")} dir="ltr" />
              <SelectField name="branch_id" label={t("pp.branch")} required requiredLabel={t("common.required")} options={branches.map((b) => ({ value: b.id, label: `${b.name} (${b.city})` }))} />
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("fp.sendInvite")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
