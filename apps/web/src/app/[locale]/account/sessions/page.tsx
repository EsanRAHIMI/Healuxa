import { unwrap } from "@healuxa/api-client";
import { formatDateTime } from "@healuxa/i18n";

import { revokeSessionAction } from "@/actions/account";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { Form } from "@/components/forms/Form";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Badge, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

export default async function SessionsPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const sessions = await settle(() => unwrap(api.identity.GET("/sessions", { params: { query: { limit: 50 } } })));
  return (
    <>
      <PageHeader title={t("account.sessions")} lead={t("account.sessionsLead")} />
      {!sessions.ok ? (
        <ServiceError error={sessions.error} locale={locale} />
      ) : sessions.value.data.length === 0 ? (
        <EmptyState title={t("account.noSessions")} />
      ) : (
        <ul className="space-y-4" data-testid="sessions">
          {sessions.value.data.map((s) => {
            const current = s.id === session.sessionId;
            return (
              <Card as="li" key={s.id} className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {s.device && s.device !== "unknown" ? s.device : t("account.unknownDevice")}
                    {current ? <Badge tone="primary">{t("account.thisDevice")}</Badge> : null}
                  </p>
                  <p className="text-sm text-text-muted">
                    {t("account.signedInAt", { date: s.created_at ? formatDateTime(s.created_at, locale) : "—" })}
                    {" · "}
                    {t("account.lastSeen", { date: s.last_seen_at ? formatDateTime(s.last_seen_at, locale) : "—" })}
                    {s.ip ? (
                      <>
                        {" · "}
                        <span className="hx-ltr-nums">{s.ip}</span>
                      </>
                    ) : null}
                  </p>
                </div>
                <Form action={revokeSessionAction} locale={locale} hidden={{ session_id: s.id ?? "" }} label={t("account.revoke")}>
                  <ConfirmButton
                    trigger={t("account.revoke")}
                    title={current ? t("account.revokeCurrentTitle") : t("account.revokeTitle")}
                    description={current ? t("account.revokeCurrentBody") : t("account.revokeBody")}
                    confirmLabel={t("account.revoke")}
                    cancelLabel={t("common.cancel")}
                    name="confirm"
                    value="1"
                    testId={`revoke-${s.id}`}
                  />
                </Form>
              </Card>
            );
          })}
        </ul>
      )}
    </>
  );
}
