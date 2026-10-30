import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ServiceError, settle } from "@/components/domain/ServiceError";
import { PortalNav } from "@/components/site/PortalNav";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyProvider } from "@/lib/portal";
import { privateMetadata } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("pp.title"));
}

export default async function ProviderPortalLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const mine = await settle(() => getMyProvider());
  const base = `/${locale}/provider`;
  return (
    <div className="hx-container py-10">
      {!mine.ok ? (
        <ServiceError error={mine.error} locale={locale} />
      ) : mine.value ? (
        <PortalNav
          label={t("pp.navLabel")}
          items={[
            { href: base, label: t("pp.overview"), exact: true },
            { href: `${base}/profile`, label: t("pp.profile") },
            { href: `${base}/credentials`, label: t("pp.credentials") },
            { href: `${base}/affiliations`, label: t("pp.affiliations") },
            { href: `${base}/services`, label: t("pp.services") },
            { href: `${base}/availability`, label: t("pp.availability") },
          ]}
        />
      ) : null}
      {children}
    </div>
  );
}
