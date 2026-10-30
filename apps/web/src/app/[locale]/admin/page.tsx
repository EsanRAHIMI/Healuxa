import { unwrap } from "@healuxa/api-client";
import Link from "next/link";

import { Card, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

/** Queue overview: how much is waiting in each staff queue (first page counts, "+" when more). */
export default async function AdminHome({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const count = async (p: Promise<{ data: unknown[]; page: { has_more: boolean } }>) =>
    p.then((r) => `${r.data.length}${r.page.has_more ? "+" : ""}`).catch(() => "—");
  const tiles: { href: string; label: string; value: Promise<string> }[] = [];
  if (hasPermission(session, "providers:verify")) {
    tiles.push({ href: `/${locale}/admin/credentials`, label: t("admin.credentialsWaiting"), value: count(unwrap(api.provider.GET("/admin/credentials", { params: { query: { status: "submitted", limit: 100 } } }))) });
    tiles.push({ href: `/${locale}/admin/providers?verification_status=verified&status=pending`, label: t("admin.awaitingActivation"), value: count(unwrap(api.provider.GET("/admin/providers", { params: { query: { status: "pending", verification_status: "verified", limit: 100 } } }))) });
  }
  if (hasPermission(session, "facilities:verify")) {
    tiles.push({ href: `/${locale}/admin/facilities`, label: t("admin.facilitiesWaiting"), value: count(unwrap(api.provider.GET("/admin/facilities", { params: { query: { verification_status: "under_review", limit: 100 } } }))) });
  }
  if (hasPermission(session, "concierge:coordinate")) {
    tiles.push({ href: `/${locale}/admin/concierge?assignee=unassigned`, label: t("admin.unassignedCases"), value: count(unwrap(api.concierge.GET("/concierge/queue", { params: { query: { assignee: "unassigned", limit: 100 } } }))) });
    tiles.push({ href: `/${locale}/admin/concierge?breached=1`, label: t("admin.slaBreached"), value: count(unwrap(api.concierge.GET("/concierge/queue", { params: { query: { breached: true, limit: 100 } } }))) });
  }
  const values = await Promise.all(tiles.map((x) => x.value));
  return (
    <>
      <PageHeader title={t("admin.overview")} lead={t("admin.lead")} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((tile, i) => (
          <Card as="li" key={tile.href}>
            <p className="text-sm text-text-muted">{tile.label}</p>
            <p className="mt-1 text-3xl font-semibold hx-ltr-nums">{values[i]}</p>
            <Link href={tile.href} className="mt-3 inline-block text-sm">
              {t("admin.openQueue")}
            </Link>
          </Card>
        ))}
      </ul>
    </>
  );
}
