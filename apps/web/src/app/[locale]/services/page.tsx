import type { Metadata } from "next";

import { OfferingCard } from "@/components/domain/cards";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CursorPager, FilterBar, FilterInput } from "@/components/ui/filters";
import { EmptyState, PageHeader } from "@/components/ui/primitives";
import { listPublicServices, offeringContext } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const filtered = Object.keys(await searchParams).length > 0;
  return pageMetadata(locale, "/services", { title: t("services.title"), description: t("services.lead"), noindex: filtered });
}

export default async function ServicesPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const category = qp(sp, "category", 80);
  const cursor = qp(sp, "cursor", 512);
  const result = await settle(async () => {
    const page = await listPublicServices({ category, cursor });
    return { page, ctx: await offeringContext(page.data) };
  });
  const base = `/${locale}/services`;
  return (
    <div className="hx-container py-12">
      <PageHeader eyebrow={t("services.eyebrow")} title={t("services.title")} lead={t("services.lead")} />
      <FilterBar action={base} label={t("services.filtersLabel")} submitLabel={t("common.search")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterInput name="category" label={t("services.category")} defaultValue={category} placeholder={t("services.categoryPlaceholder")} />
      </FilterBar>
      <p className="mt-6 max-w-3xl text-sm text-text-muted">{t("payment.feeBreakdownExplainer")}</p>
      <section aria-labelledby="results" className="mt-6">
        <h2 id="results" className="sr-only">
          {t("services.resultsHeading")}
        </h2>
        {!result.ok ? (
          <ServiceError error={result.error} locale={locale} />
        ) : result.value.page.data.length === 0 ? (
          <EmptyState title={t("services.emptyTitle")} body={t("services.emptyBody")} />
        ) : (
          <>
            <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-3" data-testid="service-results">
              {result.value.page.data.map((o) => (
                <OfferingCard
                  key={o.id}
                  offering={o}
                  locale={locale}
                  provider={result.value.ctx.providers.get(o.provider_id)}
                  facility={o.facility_id ? result.value.ctx.facilities.get(o.facility_id) : undefined}
                  branch={result.value.ctx.branches.get(o.branch_id)}
                />
              ))}
            </ul>
            <CursorPager
              basePath={base}
              params={{ category }}
              nextCursor={result.value.page.page.next_cursor}
              isFirst={!cursor}
              nextLabel={t("common.next")}
              firstLabel={t("common.firstPage")}
              navLabel={t("a11y.pagination")}
            />
          </>
        )}
      </section>
    </div>
  );
}
