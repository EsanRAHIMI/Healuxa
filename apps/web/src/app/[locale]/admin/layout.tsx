import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { PortalNav } from "@/components/site/PortalNav";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { privateMetadata } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("admin.title"));
}

/** Staff console. Sections appear per permission from the verified access token; services re-check. */
export default async function AdminLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const can = (p: string) => hasPermission(session, p);
  if (!["providers:verify", "facilities:verify", "concierge:coordinate", "payments:manage", "payments:refund", "finance:reconcile"].some(can)) notFound();
  const t = getT(locale);
  const base = `/${locale}/admin`;
  const items = [
    { href: base, label: t("admin.overview"), exact: true },
    ...(can("providers:verify") ? [{ href: `${base}/credentials`, label: t("admin.credentials") }, { href: `${base}/providers`, label: t("admin.providers") }] : []),
    ...(can("facilities:verify") ? [{ href: `${base}/facilities`, label: t("admin.facilities") }] : []),
    ...(can("concierge:coordinate") ? [{ href: `${base}/concierge`, label: t("admin.concierge") }] : []),
    ...(can("payments:manage") || can("payments:refund") || can("finance:reconcile") ? [{ href: `${base}/payments`, label: t("admin.payments") }] : []),
  ];
  return (
    <div className="hx-container py-10">
      <p className="mb-2 text-sm font-medium tracking-wide text-accent uppercase">{t("admin.title")}</p>
      <PortalNav label={t("admin.navLabel")} items={items} />
      {children}
    </div>
  );
}
