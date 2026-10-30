import { unwrap, type Provider } from "@healuxa/api-client";
import Link from "next/link";

import { createOfferingAction } from "@/actions/provider";
import { FeeBreakdown } from "@/components/domain/FeeBreakdown";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SelectField, SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { OfferingFields } from "@/components/portal/OfferingFields";
import { Alert, Card, EmptyState, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { listPublicServices } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { getBranchesAs } from "@/lib/portal";

/** Offerings of affiliated practitioners at this facility; facility_admins may create/edit them. */
export default async function FacilityOfferings({ params }: { params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  const t = getT(locale);
  const api = await userApi();
  const data = await settle(async () => {
    const [affs, branches, offerings] = await Promise.all([
      unwrap(api.provider.GET("/facilities/{facility_id}/affiliations", { params: { path: { facility_id: facilityId } } })),
      getBranchesAs(facilityId),
      listPublicServices({ facility_id: facilityId, limit: 100 }),
    ]);
    const active = affs.data.filter((a) => a.status === "active");
    const providers = new Map<string, Provider>();
    await Promise.all(
      [...new Set(active.map((a) => a.provider_id))].map(async (id) => {
        const p = await unwrap(api.provider.GET("/providers/{id}", { params: { path: { id } } })).catch(() => null);
        if (p) providers.set(id, p);
      }),
    );
    return { active, branches: new Map(branches.map((b) => [b.id, b])), offerings: offerings.data, providers };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const { active, branches, offerings, providers } = data.value;
  const practiceOptions = active.map((a) => ({
    value: `${a.provider_id}|${a.branch_id}`,
    label: `${providers.get(a.provider_id)?.display_name ?? a.provider_id} — ${branches.get(a.branch_id)?.name ?? a.branch_id}`,
  }));
  return (
    <>
      <Section title={t("fp.offerings")} description={t("fp.offeringsLead")} id="list">
        {offerings.length === 0 ? (
          <EmptyState title={t("facility.noOfferings")} />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {offerings.map((o) => (
              <Card as="li" key={o.id} className="flex flex-col gap-3">
                <h3 className="text-lg">{o.name}</h3>
                <p className="text-sm text-text-muted">
                  {providers.get(o.provider_id)?.display_name ?? o.provider_id} · {branches.get(o.branch_id)?.name ?? ""}
                </p>
                <FeeBreakdown offering={o} locale={locale} />
                <Link href={`/${locale}/provider/services/${o.id}?facility=${facilityId}`} className="mt-auto text-sm">
                  {t("common.edit")}
                </Link>
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("pp.addOffering")} id="create">
        {practiceOptions.length === 0 ? (
          <Alert tone="info" role="note" title={t("fp.needAffiliation")} />
        ) : (
          <Card className="max-w-3xl">
            <Form action={createOfferingAction} locale={locale} label={t("pp.addOffering")} resetOnSuccess testId="facility-offering-form">
              <SelectField name="practice" label={t("fp.practitioner")} required requiredLabel={t("common.required")} options={practiceOptions} className="mb-5" />
              <OfferingFields locale={locale} />
              <div className="mt-6">
                <SubmitButton pendingLabel={t("common.saving")}>{t("pp.addOffering")}</SubmitButton>
              </div>
            </Form>
          </Card>
        )}
      </Section>
    </>
  );
}
