import { unwrap, type ConciergeMessage } from "@healuxa/api-client";
import { formatDateTime, type Locale } from "@healuxa/i18n";

import { postMessageAction } from "@/actions/concierge";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SubmitButton, TextArea } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { cn } from "@/components/ui/cn";
import { userApi } from "@/lib/api";
import { getT } from "@/lib/i18n";

async function loadAll(caseId: string): Promise<ConciergeMessage[]> {
  const api = await userApi();
  const out: ConciergeMessage[] = [];
  let cursor: string | undefined;
  for (let i = 0; i < 10; i++) {
    const page = await unwrap(api.concierge.GET("/concierge/cases/{id}/messages", { params: { path: { id: caseId }, query: { limit: 100, cursor } } }));
    out.push(...page.data);
    if (!page.page.has_more || !page.page.next_cursor) break;
    cursor = page.page.next_cursor;
  }
  return out;
}

/**
 * Secure customer<->coordinator thread (concierge-service). Opening the thread marks the
 * counterparty's messages read (read receipts). Bodies stay in concierge-service; never logged here.
 */
export async function MessageThread({ caseId, locale, viewerRole, canPost }: { caseId: string; locale: Locale; viewerRole: "customer" | "coordinator"; canPost: boolean }) {
  const t = getT(locale);
  const res = await settle(() => loadAll(caseId));
  if (!res.ok) return <ServiceError error={res.error} locale={locale} />;
  const messages = res.value;
  if (messages.some((m) => m.sender_role !== viewerRole && !m.read_at)) {
    const api = await userApi();
    await unwrap(api.concierge.POST("/concierge/cases/{id}/messages/read", { params: { path: { id: caseId } }, body: {} })).catch(() => undefined);
  }
  return (
    <div className="space-y-4">
      {messages.length === 0 ? (
        <p className="text-text-muted">{t("concierge.noMessages")}</p>
      ) : (
        <ol className="space-y-3" aria-label={t("concierge.messages")} data-testid="messages">
          {messages.map((m) => {
            const mine = m.sender_role === viewerRole;
            return (
              <li key={m.id} className={cn("max-w-[85%] rounded-lg px-4 py-3", mine ? "ms-auto bg-primary-soft text-on-primary-soft" : "me-auto border border-border bg-surface")}>
                <p className="text-xs text-text-muted">
                  {mine ? t("concierge.you") : t(`concierge.role_${m.sender_role}`)} · <span className="hx-ltr-nums">{formatDateTime(m.created_at, locale, { dateStyle: "short", timeStyle: "short" })}</span>
                  {mine && m.read_at ? ` · ${t("concierge.read")}` : ""}
                </p>
                <p className="mt-1 whitespace-pre-wrap">{m.body}</p>
              </li>
            );
          })}
        </ol>
      )}
      {canPost ? (
        <Form action={postMessageAction} locale={locale} hidden={{ case_id: caseId }} label={t("concierge.sendMessage")} resetOnSuccess showSuccess={false} testId="message-form">
          <TextArea name="body" label={t("concierge.newMessage")} hint={viewerRole === "customer" ? t("concierge.noClinicalHint") : undefined} required requiredLabel={t("common.required")} maxLength={4000} />
          <div className="mt-3">
            <SubmitButton pendingLabel={t("concierge.sending")}>{t("concierge.sendMessage")}</SubmitButton>
          </div>
        </Form>
      ) : (
        <p className="text-sm text-text-muted">{t("concierge.messagingUnavailable")}</p>
      )}
    </div>
  );
}
