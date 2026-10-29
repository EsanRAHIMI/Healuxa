import { Card, DefinitionList, PageHeader, ButtonLink } from "@/components/ui/primitives";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

export default async function AccountPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const isStaff = hasPermission(session, "providers:verify") || hasPermission(session, "facilities:verify");
  const cards = [
    { href: `/${locale}/account/profile`, title: t("account.privacyPrefs"), body: t("account.privacyPrefsBody") },
    { href: `/${locale}/account/sessions`, title: t("account.sessions"), body: t("account.sessionsBody") },
    ...(hasPermission(session, "providers:onboard") ? [{ href: `/${locale}/provider`, title: t("nav.forProviders"), body: t("account.providerBody") }] : []),
    ...(hasPermission(session, "facilities:onboard") ? [{ href: `/${locale}/facility`, title: t("nav.forFacilities"), body: t("account.facilityBody") }] : []),
    ...(isStaff ? [{ href: `/${locale}/admin`, title: t("nav.admin"), body: t("account.adminBody") }] : []),
  ];
  return (
    <>
      <PageHeader title={t("account.title")} lead={t("account.lead")} />
      <Card className="mb-8">
        <DefinitionList
          items={[
            { term: t("account.accountId"), value: <span className="hx-ltr-nums break-all" data-testid="account-id">{session.userId}</span> },
            { term: t("account.roles"), value: session.roles.length ? session.roles.join(", ") : t("common.none") },
          ]}
        />
      </Card>
      <ul className="grid gap-5 md:grid-cols-2">
        {cards.map((c) => (
          <Card as="li" key={c.href} className="flex flex-col gap-3">
            <h2 className="text-xl">{c.title}</h2>
            <p className="text-text-muted">{c.body}</p>
            <div className="mt-auto">
              <ButtonLink href={c.href} variant="secondary" size="sm">
                {t("common.open")}
              </ButtonLink>
            </div>
          </Card>
        ))}
      </ul>
      <p className="mt-8 text-sm text-text-muted">{t("account.bookingsPending")}</p>
    </>
  );
}
