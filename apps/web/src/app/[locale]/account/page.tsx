import { deleteAccountAction } from "@/actions/account";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { ButtonLink, Card, DefinitionList, PageHeader, Section } from "@/components/ui/primitives";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

/** Account hub: links to every customer area and the role-gated portals, plus account deletion. */
export default async function AccountPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const isStaff = ["providers:verify", "facilities:verify", "concierge:coordinate", "payments:manage", "payments:refund", "finance:reconcile"].some((p) => hasPermission(session, p));
  const base = `/${locale}/account`;
  const cards = [
    { href: `${base}/bookings`, title: t("bookings.title"), body: t("bookings.lead") },
    { href: `${base}/concierge`, title: t("concierge.title"), body: t("concierge.lead") },
    { href: `${base}/notifications`, title: t("notifications.title"), body: t("notifications.lead") },
    { href: `${base}/payments`, title: t("payments.title"), body: t("payments.lead") },
    { href: `${base}/profile`, title: t("account.privacyPrefs"), body: t("account.privacyPrefsBody") },
    { href: `${base}/sessions`, title: t("account.sessions"), body: t("account.sessionsBody") },
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
      <ul className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
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
      <Section title={t("account.deleteTitle")} description={t("account.deleteLead")} id="delete">
        <Card className="max-w-xl border-danger">
          <Form action={deleteAccountAction} locale={locale} label={t("account.deleteTitle")} showSuccess={false} testId="delete-account-form">
            <div className="space-y-4">
              <TextField name="password" type="password" label={t("auth.password")} required requiredLabel={t("common.required")} autoComplete="current-password" />
              <TextField name="confirm_text" label={t("account.deleteConfirmLabel")} hint={t("account.deleteConfirmHint")} required requiredLabel={t("common.required")} autoComplete="off" dir="ltr" />
              <ConfirmButton trigger={t("account.deleteButton")} title={t("account.deleteTitle")} description={t("account.deleteWarning")} confirmLabel={t("account.deleteButton")} cancelLabel={t("common.cancel")} name="confirm" value="1" />
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
