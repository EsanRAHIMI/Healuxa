import { languageName } from "@healuxa/i18n";
import type { Metadata } from "next";

import { ProviderCard } from "@/components/domain/cards";
import { NearMeButton } from "@/components/domain/NearMeButton";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CursorPager, FilterBar, FilterInput, FilterSelect } from "@/components/ui/filters";
import { EmptyState, PageHeader } from "@/components/ui/primitives";
import { searchProviders } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { LANGUAGE_CODES, PROVIDER_TYPES, oneOf, parseNear, qp } from "@/lib/query";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const filtered = Object.keys(await searchParams).length > 0;
  // Filtered result pages are not indexed separately (canonical = unfiltered directory).
  return pageMetadata(locale, "/providers", { title: t("providers.title"), description: t("providers.lead"), noindex: filtered });
}

const RADII = ["2", "5", "10", "25", "50"];

export default async function ProvidersPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const filters = {
    type: oneOf(qp(sp, "type"), PROVIDER_TYPES),
    specialty: qp(sp, "specialty", 80),
    language: oneOf(qp(sp, "language"), LANGUAGE_CODES),
    city: qp(sp, "city", 100),
    near: parseNear(qp(sp, "near", 40)),
    radius_km: oneOf(qp(sp, "radius_km"), RADII),
  };
  const cursor = qp(sp, "cursor", 512);
  const result = await settle(() =>
    searchProviders({
      ...filters,
      radius_km: filters.near && filters.radius_km ? Number(filters.radius_km) : undefined,
      cursor,
    }),
  );
  const base = `/${locale}/providers`;
  return (
    <div className="hx-container py-12">
      <PageHeader eyebrow={t("providers.eyebrow")} title={t("providers.title")} lead={t("providers.lead")} />
      <FilterBar action={base} label={t("providers.filtersLabel")} submitLabel={t("common.search")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterInput name="specialty" label={t("providers.specialty")} defaultValue={filters.specialty} placeholder={t("providers.specialtyPlaceholder")} />
        <FilterSelect
          name="language"
          label={t("providers.language")}
          defaultValue={filters.language}
          anyLabel={t("providers.anyLanguage")}
          options={LANGUAGE_CODES.map((c) => ({ value: c, label: languageName(c, locale) }))}
        />
        <FilterInput name="city" label={t("providers.city")} defaultValue={filters.city} placeholder={t("providers.cityPlaceholder")} />
        <FilterSelect
          name="type"
          label={t("providers.type")}
          defaultValue={filters.type}
          anyLabel={t("providers.anyType")}
          options={PROVIDER_TYPES.map((v) => ({ value: v, label: t(`enums.providerType.${v}`) }))}
        />
        <div className="sm:col-span-2">
          <FilterInput id="filter-near" name="near" label={t("providers.near")} defaultValue={filters.near} placeholder="25.2048,55.2708" inputMode="decimal" />
          <div className="mt-2">
            <NearMeButton targetId="filter-near" label={t("providers.useLocation")} busyLabel={t("providers.locating")} deniedLabel={t("providers.locationDenied")} />
          </div>
        </div>
        <FilterSelect
          name="radius_km"
          label={t("providers.radius")}
          defaultValue={filters.radius_km}
          anyLabel={t("providers.radiusDefault")}
          options={RADII.map((r) => ({ value: r, label: t("providers.radiusKm", { km: Number(r) }) }))}
        />
      </FilterBar>

      <section aria-labelledby="results" className="mt-8">
        <h2 id="results" className="sr-only">
          {t("providers.resultsHeading")}
        </h2>
        {!result.ok ? (
          <ServiceError error={result.error} locale={locale} />
        ) : result.value.data.length === 0 ? (
          <EmptyState title={t("providers.emptyTitle")} body={t("providers.emptyBody")} />
        ) : (
          <>
            <p className="mb-4 text-sm text-text-muted" role="status">
              {t("providers.showing", { count: result.value.data.length })}
            </p>
            <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-3" data-testid="provider-results">
              {result.value.data.map((p) => (
                <ProviderCard key={p.id} provider={p} locale={locale} />
              ))}
            </ul>
            <CursorPager
              basePath={base}
              params={{ ...filters }}
              nextCursor={result.value.page.next_cursor}
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
