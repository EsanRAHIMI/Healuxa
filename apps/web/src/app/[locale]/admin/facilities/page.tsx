import { unwrap } from "@healuxa/api-client";
import { formatDate } from "@healuxa/i18n";

import { reviewFacilityAction } from "@/actions/admin";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { DecisionForm } from "@/components/portal/DecisionForm";
import { CursorPager } from "@/components/ui/filters";
import { Card, DefinitionList, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

/** Facility licence verification queue; verifying also activates the facility (provider-service rule). */
export default async function FacilityQueue({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const cursor = qp(await searchParams, "cursor", 512);
  const api = await userApi();
  const res = await settle(() => unwrap(api.provider.GET("/admin/facilities", { params: { query: { verification_status: "under_review", limit: 20, cursor } } })));
  return (
    <>
      <PageHeader title={t("admin.facilities")} lead={t("admin.facilitiesLead")} />
      {!res.ok ? (
        <ServiceError error={res.error} locale={locale} />
      ) : res.value.data.length === 0 ? (
        <EmptyState title={t("admin.queueEmpty")} />
      ) : (
        <ul className="space-y-4" data-testid="facility-queue">
          {res.value.data.map((f) => (
            <Card as="li" key={f.id} className="grid gap-6 lg:grid-cols-[3fr_2fr]" data-testid="queue-facility">
              <div>
                <p className="text-lg font-medium">{f.name}</p>
                <DefinitionList
                  className="mt-3"
                  items={[
                    { term: t("fp.type"), value: t(`enums.facilityType.${f.type}`) },
                    { term: t("fp.licenceAuthority"), value: f.license_authority ?? "—" },
                    { term: t("fp.licenceNumber"), value: <span className="hx-ltr-nums">{f.license_number ?? "—"}</span> },
                    ...(f.website ? [{ term: t("fp.website"), value: <span dir="ltr">{f.website}</span> }] : []),
                    ...(f.created_at ? [{ term: t("admin.submittedAt"), value: formatDate(f.created_at, locale) }] : []),
                    { term: t("common.id"), value: <span className="hx-ltr-nums text-sm">{f.id}</span> },
                  ]}
                />
              </div>
              <DecisionForm action={reviewFacilityAction} locale={locale} hidden={{ facility_id: f.id }} testId="facility-decision" />
            </Card>
          ))}
        </ul>
      )}
      {res.ok ? (
        <CursorPager basePath={`/${locale}/admin/facilities`} params={{}} nextCursor={res.value.page.next_cursor} isFirst={!cursor} nextLabel={t("common.next")} firstLabel={t("common.firstPage")} navLabel={t("a11y.pagination")} />
      ) : null}
    </>
  );
}
