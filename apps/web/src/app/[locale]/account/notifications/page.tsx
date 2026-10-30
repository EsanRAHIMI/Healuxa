import { unwrap } from "@healuxa/api-client";
import { formatDateTime } from "@healuxa/i18n";
import Link from "next/link";

import { markReadAction } from "@/actions/notifications";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { cn } from "@/components/ui/cn";
import { Badge, ButtonLink, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

/** Link a notification to the page of the entity it is about. */
function entityHref(locale: string, type?: string | null, id?: string | null): string | null {
  if (!type || !id) return null;
  if (type === "appointment") return `/${locale}/account/bookings/${id}`;
  if (type === "concierge_case") return `/${locale}/account/concierge/${id}`;
  if (type === "provider") return `/${locale}/provider`;
  if (type === "facility") return `/${locale}/facility/${id}`;
  return null;
}

export default async function Inbox({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const sp = await searchParams;
  const unreadOnly = qp(sp, "unread") === "1";
  const cursor = qp(sp, "cursor", 512);
  const api = await userApi();
  const res = await settle(() => unwrap(api.notification.GET("/notifications", { params: { query: { unread_only: unreadOnly, limit: 30, cursor } } })));
  return (
    <>
      <PageHeader
        title={t("notifications.title")}
        lead={t("notifications.lead")}
        actions={
          <>
            <ButtonLink href={`/${locale}/account/notifications/preferences`} variant="secondary" size="sm">
              {t("notifications.preferences")}
            </ButtonLink>
            <Form action={markReadAction} locale={locale} showSuccess={false} label={t("notifications.markAll")}>
              <SubmitButton variant="ghost" pendingLabel={t("common.saving")}>{t("notifications.markAll")}</SubmitButton>
            </Form>
          </>
        }
      />
      <nav aria-label={t("notifications.title")} className="mb-6 flex gap-4 text-sm">
        <Link href={`/${locale}/account/notifications`} aria-current={!unreadOnly ? "page" : undefined}>{t("notifications.all")}</Link>
        <Link href={`/${locale}/account/notifications?unread=1`} aria-current={unreadOnly ? "page" : undefined}>{t("notifications.unread")}</Link>
      </nav>
      {!res.ok ? (
        <ServiceError error={res.error} locale={locale} />
      ) : res.value.data.length === 0 ? (
        <EmptyState title={t("notifications.empty")} />
      ) : (
        <>
          <ul className="space-y-3" data-testid="notifications">
            {res.value.data.map((n) => {
              const href = entityHref(locale, n.entity_type, n.entity_id);
              return (
                <Card as="li" key={n.id} className={cn("flex flex-wrap items-start justify-between gap-3", !n.read_at && "border-primary")}>
                  <div lang={n.locale}>
                    <p className="flex items-center gap-2 font-medium">
                      {!n.read_at ? <Badge tone="primary">{t("notifications.new")}</Badge> : null}
                      {href ? <Link href={href}>{n.title}</Link> : n.title}
                    </p>
                    <p className="mt-1 text-sm">{n.body}</p>
                    <p className="mt-1 text-xs text-text-muted hx-ltr-nums">{formatDateTime(n.created_at, locale)}</p>
                  </div>
                  {!n.read_at ? (
                    <Form action={markReadAction} locale={locale} hidden={{ notification_id: n.id }} showSuccess={false} label={t("notifications.markRead")}>
                      <SubmitButton variant="ghost" pendingLabel={t("common.saving")}>{t("notifications.markRead")}</SubmitButton>
                    </Form>
                  ) : null}
                </Card>
              );
            })}
          </ul>
          {res.value.page.next_cursor ? (
            <div className="mt-6">
              <ButtonLink href={`/${locale}/account/notifications?${unreadOnly ? "unread=1&" : ""}cursor=${encodeURIComponent(res.value.page.next_cursor)}`} variant="secondary">
                {t("common.next")}
              </ButtonLink>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
