import { unwrap } from "@healuxa/api-client";
import Link from "next/link";

import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CursorPager, FilterBar, FilterSelect } from "@/components/ui/filters";
import { Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { oneOf, qp } from "@/lib/query";

const STATUSES = ["pending", "active", "suspended", "offboarded"] as const;
const VERIFICATION = ["unverified", "under_review", "verified", "rejected"] as const;

export default async function AdminProviders({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const filters = { status: oneOf(qp(sp, "status"), STATUSES), verification_status: oneOf(qp(sp, "verification_status"), VERIFICATION) };
  const cursor = qp(sp, "cursor", 512);
  const api = await userApi();
  const res = await settle(() => unwrap(api.provider.GET("/admin/providers", { params: { query: { ...filters, limit: 25, cursor } } })));
  const base = `/${locale}/admin/providers`;
  return (
    <>
      <PageHeader title={t("admin.providers")} lead={t("admin.providersLead")} />
      <FilterBar action={base} label={t("common.filter")} submitLabel={t("common.apply")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterSelect name="status" label={t("common.status")} defaultValue={filters.status} anyLabel={t("admin.any")} options={STATUSES.map((s) => ({ value: s, label: t(`enums.providerStatus.${s}`) }))} />
        <FilterSelect name="verification_status" label={t("pp.verification")} defaultValue={filters.verification_status} anyLabel={t("admin.any")} options={VERIFICATION.map((s) => ({ value: s, label: t(`enums.verificationStatus.${s}`) }))} />
      </FilterBar>
      <div className="mt-6">
        {!res.ok ? (
          <ServiceError error={res.error} locale={locale} />
        ) : res.value.data.length === 0 ? (
          <EmptyState title={t("admin.queueEmpty")} />
        ) : (
          <ul className="space-y-3" data-testid="admin-providers">
            {res.value.data.map((p) => (
              <Card as="li" key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3 md:py-3">
                <Link href={`${base}/${p.id}`} className="font-medium">
                  {p.display_name}
                </Link>
                <div className="flex flex-wrap gap-2">
                  <VerificationBadge status={p.verification_status} locale={locale} />
                  <StatusBadge status={p.status} kind="providerStatus" locale={locale} />
                </div>
              </Card>
            ))}
          </ul>
        )}
      </div>
      {res.ok ? <CursorPager basePath={base} params={filters} nextCursor={res.value.page.next_cursor} isFirst={!cursor} nextLabel={t("common.next")} firstLabel={t("common.firstPage")} navLabel={t("a11y.pagination")} /> : null}
    </>
  );
}
