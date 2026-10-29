import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PortalNav } from "@/components/site/PortalNav";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { privateMetadata } from "@/lib/seo";

type Props = { children: ReactNode; params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("account.title"));
}

export default async function AccountLayout({ children, params }: Props) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const base = `/${locale}/account`;
  return (
    <div className="hx-container py-10">
      <PortalNav
        label={t("account.navLabel")}
        items={[
          { href: base, label: t("account.overview"), exact: true },
          { href: `${base}/profile`, label: t("account.privacyPrefs") },
          { href: `${base}/sessions`, label: t("account.sessions") },
        ]}
      />
      {children}
    </div>
  );
}
