import type { Metadata } from "next";

import { FacilityCard } from "@/components/domain/cards";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CursorPager, FilterBar, FilterInput, FilterSelect } from "@/components/ui/filters";
import { EmptyState, PageHeader } from "@/components/ui/primitives";
import { listPublicBranches, searchFacilities } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { FACILITY_TYPES, oneOf, qp } from "@/lib/query";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const filtered = Object.keys(await searchParams).length > 0;
  return pageMetadata(locale, "/facilities", { title: t("facilities.title"), description: t("facilities.lead"), noindex: filtered });
}

export default async function FacilitiesPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const filters = { type: oneOf(qp(sp, "type"), FACILITY_TYPES), city: qp(sp, "city", 100) };
  const cursor = qp(sp, "cursor", 512);
  const result = await settle(async () => {
    const page = await searchFacilities({ ...filters, cursor });
    const cities = await Promise.all(
      page.data.map(async (f) => [f.id, [...new Set((await listPublicBranches(f.id).catch(() => [])).map((b) => b.city))]] as const),
    );
    return { page, cities: new Map(cities) };
  });
  const base = `/${locale}/facilities`;
  return (
    <div className="hx-container py-12">
      <PageHeader eyebrow={t("facilities.eyebrow")} title={t("facilities.title")} lead={t("facilities.lead")} />
      <FilterBar action={base} label={t("facilities.filtersLabel")} submitLabel={t("common.search")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterSelect
          name="type"
          label={t("facilities.type")}
          defaultValue={filters.type}
          anyLabel={t("facilities.anyType")}
          options={FACILITY_TYPES.map((v) => ({ value: v, label: t(`enums.facilityType.${v}`) }))}
        />
        <FilterInput name="city" label={t("providers.city")} defaultValue={filters.city} placeholder={t("providers.cityPlaceholder")} />
      </FilterBar>
      <section aria-labelledby="results" className="mt-8">
        <h2 id="results" className="sr-only">
          {t("facilities.resultsHeading")}
        </h2>
        {!result.ok ? (
          <ServiceError error={result.error} locale={locale} />
        ) : result.value.page.data.length === 0 ? (
          <EmptyState title={t("facilities.emptyTitle")} body={t("facilities.emptyBody")} />
        ) : (
          <>
            <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-3" data-testid="facility-results">
              {result.value.page.data.map((f) => (
                <FacilityCard key={f.id} facility={f} locale={locale} cities={result.value.cities.get(f.id)} />
              ))}
            </ul>
            <CursorPager
              basePath={base}
              params={filters}
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
