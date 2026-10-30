import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { PortalNav } from "@/components/site/PortalNav";
import { getT, resolveLocale } from "@/lib/i18n";
import { getFacilityAs } from "@/lib/portal";

/** Facility workspace: only rendered for the facility's staff (private view has licence fields). */
export default async function FacilityWorkspaceLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  if (!/^[A-Za-z0-9-]{10,36}$/.test(facilityId)) notFound();
  const t = getT(locale);
  const facility = await getFacilityAs(facilityId);
  if (!facility || facility.license_number == null) notFound();
  const base = `/${locale}/facility/${facility.id}`;
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl">{facility.name}</h1>
        <VerificationBadge status={facility.verification_status} locale={locale} />
        <StatusBadge status={facility.status} kind="providerStatus" locale={locale} />
      </div>
      <PortalNav
        label={t("fp.navLabel")}
        items={[
          { href: base, label: t("fp.overview"), exact: true },
          { href: `${base}/branches`, label: t("fp.branches") },
          { href: `${base}/staff`, label: t("fp.staff") },
          { href: `${base}/affiliations`, label: t("pp.affiliations") },
          { href: `${base}/offerings`, label: t("fp.offerings") },
          { href: `${base}/bookings`, label: t("bookings.calendar") },
        ]}
      />
      {children}
    </>
  );
}
