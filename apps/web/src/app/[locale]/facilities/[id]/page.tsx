import type { OperatingHours } from "@healuxa/api-client";
import { regionName } from "@healuxa/i18n";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { OfferingCard } from "@/components/domain/cards";
import { JsonLd } from "@/components/domain/JsonLd";
import { OpeningHoursTable } from "@/components/domain/OpeningHours";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { getPublicFacility, getPublicHours, listPublicBranches, listPublicServices, offeringContext } from "@/lib/catalog";
import { env } from "@/lib/env";
import { getT, localized, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";
import { facilityStructuredData } from "@/lib/structured-data";

type Props = { params: Promise<{ locale: string; id: string }> };

const safeId = (id: string) => /^[A-Za-z0-9-]{10,36}$/.test(id);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  const facility = safeId(id) ? await getPublicFacility(id).catch(() => null) : null;
  if (!facility) return { title: t("errors.notFoundTitle"), robots: { index: false } };
  return pageMetadata(locale, `/facilities/${facility.id}`, {
    title: facility.name,
    description: localized(facility.description ?? null, locale)?.slice(0, 160) ?? t(`enums.facilityType.${facility.type}`),
  });
}

export default async function FacilityPage({ params }: Props) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  if (!safeId(id)) notFound();
  const facility = await getPublicFacility(id);
  if (!facility) notFound();

  const branches = await listPublicBranches(facility.id);
  const hoursEntries = await Promise.all(branches.map(async (b) => [b.id, await getPublicHours(b.id).catch(() => null)] as const));
  const hours = new Map(hoursEntries.filter((e): e is readonly [string, OperatingHours] => !!e[1]));
  const offerings = await settle(async () => {
    const page = await listPublicServices({ facility_id: facility.id, limit: 50 });
    return { page, ctx: await offeringContext(page.data) };
  });
  const url = `${env.siteUrl}/${locale}/facilities/${facility.id}`;
  const ld = facilityStructuredData(facility, url, branches, hours);
  const description = localized(facility.description ?? null, locale);

  return (
    <div className="hx-container py-12">
      {ld ? <JsonLd data={ld} /> : null}
      <nav aria-label={t("a11y.breadcrumb")} className="mb-6 text-sm">
        <ol className="flex flex-wrap gap-2 text-text-muted">
          <li>
            <Link href={`/${locale}/facilities`}>{t("facilities.title")}</Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page">{facility.name}</li>
        </ol>
      </nav>
      <PageHeader eyebrow={t(`enums.facilityType.${facility.type}`)} title={facility.name} lead={description ?? undefined} actions={<VerificationBadge status={facility.verification_status} locale={locale} />} />
      {facility.website || facility.phone ? (
        <p className="-mt-4 mb-8 flex flex-wrap gap-4 text-sm">
          {facility.website ? (
            <a href={facility.website} rel="noopener noreferrer nofollow" target="_blank">
              {t("facility.website")}
              <span className="sr-only"> {t("a11y.externalLink")}</span>
            </a>
          ) : null}
          {facility.phone ? (
            <a href={`tel:${facility.phone.replace(/[^+\d]/g, "")}`} dir="ltr" className="hx-ltr-nums">
              {facility.phone}
            </a>
          ) : null}
        </p>
      ) : null}

      <Section title={t("facility.branches")} id="branches">
        {branches.length === 0 ? (
          <EmptyState title={t("facility.noBranches")} />
        ) : (
          <ul className="grid gap-5 md:grid-cols-2" data-testid="branches">
            {branches.map((b) => (
              <Card as="li" key={b.id} data-testid="branch">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-xl">{b.name}</h3>
                  <StatusBadge status={b.status ?? "active"} kind="branchStatus" locale={locale} />
                </div>
                <address className="mt-2 text-text-muted not-italic">
                  {b.address_line}
                  <br />
                  {[b.city, b.emirate, regionName(b.country, locale)].filter(Boolean).join(", ")}
                </address>
                {b.phone ? (
                  <p className="mt-1">
                    <a href={`tel:${b.phone.replace(/[^+\d]/g, "")}`} dir="ltr" className="hx-ltr-nums">
                      {b.phone}
                    </a>
                  </p>
                ) : null}
                <div className="mt-4">
                  {hours.get(b.id) && hours.get(b.id)!.windows.length ? (
                    <OpeningHoursTable hours={hours.get(b.id)!} locale={locale} />
                  ) : (
                    <p className="text-sm text-text-muted">{t("facility.hoursUnavailable")}</p>
                  )}
                </div>
              </Card>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t("facility.offerings")} description={t("payment.feeBreakdownExplainer")} id="offerings">
        {!offerings.ok ? (
          <ServiceError error={offerings.error} locale={locale} />
        ) : offerings.value.page.data.length === 0 ? (
          <EmptyState title={t("facility.noOfferings")} />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {offerings.value.page.data.map((o) => (
              <OfferingCard key={o.id} offering={o} locale={locale} provider={offerings.value.ctx.providers.get(o.provider_id)} branch={offerings.value.ctx.branches.get(o.branch_id)} />
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
