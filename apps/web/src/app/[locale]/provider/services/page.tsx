import { unwrap } from "@healuxa/api-client";
import Link from "next/link";
import { redirect } from "next/navigation";

import { createOfferingAction } from "@/actions/provider";
import { StatusBadge } from "@/components/domain/badges";
import { FeeBreakdown } from "@/components/domain/FeeBreakdown";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { OfferingFields } from "@/components/portal/OfferingFields";
import { Alert, Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { listPublicServices } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { branchLabels, getMyProvider } from "@/lib/portal";

export default async function ProviderServices({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  const { provider } = mine;
  const api = await userApi();
  const data = await settle(async () => {
    const [affs, offerings] = await Promise.all([
      unwrap(api.provider.GET("/providers/{id}/affiliations", { params: { path: { id: provider.id } } })),
      listPublicServices({ provider_id: provider.id, limit: 100 }),
    ]);
    const active = affs.data.filter((a) => a.status === "active");
    const labels = await branchLabels(active.map((a) => a.facility_id));
    return { active, offerings: offerings.data, labels };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const { active, offerings, labels } = data.value;
  const branchOptions = active.map((a) => {
    const l = labels.get(a.branch_id);
    return { value: a.branch_id, label: l ? `${l.facility} — ${l.branch.name} (${l.branch.city})` : a.branch_id };
  });
  return (
    <>
      <PageHeader title={t("pp.services")} lead={t("pp.servicesLead")} />
      <Section title={t("pp.publishedOfferings")} description={t("pp.publishedOfferingsLead")} id="list">
        {offerings.length === 0 ? (
          <EmptyState title={t("pp.noOfferings")} />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {offerings.map((o) => (
              <Card as="li" key={o.id} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-lg">{o.name}</h3>
                  <StatusBadge status={o.status} kind="offeringStatus" locale={locale} />
                </div>
                <p className="text-sm text-text-muted">{labels.get(o.branch_id)?.facility ?? ""}</p>
                <FeeBreakdown offering={o} locale={locale} />
                <Link href={`/${locale}/provider/services/${o.id}`} className="mt-auto text-sm">
                  {t("common.edit")}
                </Link>
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("pp.addOffering")} id="create">
        {branchOptions.length === 0 ? (
          <Alert tone="info" role="note" title={t("pp.needActiveAffiliation")}>
            <Link href={`/${locale}/provider/affiliations`}>{t("pp.affiliations")}</Link>
          </Alert>
        ) : (
          <Card className="max-w-3xl">
            <Form action={createOfferingAction} locale={locale} label={t("pp.addOffering")} hidden={{ provider_id: provider.id }} resetOnSuccess testId="offering-form">
              <OfferingFields locale={locale} branches={branchOptions} />
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
