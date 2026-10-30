import { NotFoundError, unwrap } from "@healuxa/api-client";
import { formatDate, formatDateTime, formatList, languageName } from "@healuxa/i18n";
import { notFound } from "next/navigation";

import { addNoteAction, assignCaseAction, escalateCaseAction, proposeOptionAction, transitionCaseAction } from "@/actions/concierge";
import { StatusBadge } from "@/components/domain/badges";
import { MessageThread } from "@/components/concierge/MessageThread";
import { SelectField, SubmitButton, TextArea, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Badge, Card, DefinitionList, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

const NEXT: Record<string, string[]> = {
  submitted: ["triaged", "cancelled"],
  triaged: ["assigned", "cancelled"],
  assigned: ["in_progress", "cancelled"],
  in_progress: ["awaiting_customer", "arranged", "cancelled"],
  awaiting_customer: ["in_progress", "arranged", "cancelled"],
  arranged: ["completed", "in_progress"],
  escalated: ["in_progress", "cancelled"],
};

/** Coordinator workspace for one case: state machine, notes (internal), options, secure messages, audit. */
export default async function CoordinatorCase({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  const session = await getSession();
  const api = await userApi();
  const c = await unwrap(api.concierge.GET("/concierge/cases/{id}", { params: { path: { id } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const [notes, options, audit] = await Promise.all([
    unwrap(api.concierge.GET("/concierge/cases/{id}/notes", { params: { path: { id } } })).then((r) => r.data).catch(() => []),
    unwrap(api.concierge.GET("/concierge/cases/{id}/options", { params: { path: { id } } })).then((r) => r.data).catch(() => []),
    unwrap(api.concierge.GET("/concierge/cases/{id}/audit", { params: { path: { id } } })).then((r) => r.data).catch(() => []),
  ]);
  const mine = c.coordinator_id === session?.userId;
  const supervisor = hasPermission(session, "concierge:supervise");
  const next = NEXT[c.status] ?? [];
  return (
    <>
      <PageHeader
        title={t(`enums.caseCategory.${c.category}`)}
        lead={t("admin.caseLead", { created: formatDateTime(c.created_at, locale) })}
        actions={
          <div className="flex gap-2">
            <StatusBadge status={c.status} kind="caseStatus" locale={locale} />
            {c.sla_breached ? <Badge tone="danger">{t("admin.slaBreached")}</Badge> : null}
          </div>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-8">
          <Card>
            <DefinitionList
              items={[
                { term: t("admin.customer"), value: <span className="hx-ltr-nums text-sm">{c.customer_id}</span> },
                ...(c.preferred_start_date ? [{ term: t("concierge.dates"), value: `${formatDate(c.preferred_start_date, locale)}${c.preferred_end_date ? ` – ${formatDate(c.preferred_end_date, locale)}` : ""}` }] : []),
                ...(c.destination_city ? [{ term: t("concierge.city"), value: c.destination_city }] : []),
                { term: t("concierge.languages"), value: c.languages.length ? formatList(c.languages.map((l) => languageName(l, locale)), locale) : "—" },
                { term: t("admin.firstResponse"), value: <span className="hx-ltr-nums">{formatDateTime(c.first_response_due_at, locale)}</span> },
                { term: t("concierge.coordinator"), value: c.coordinator_id ? (mine ? t("concierge.you") : <span className="hx-ltr-nums text-sm">{c.coordinator_id}</span>) : t("concierge.assignedNo") },
              ]}
            />
            {c.needs_note ? <p className="mt-4 whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-sm">{c.needs_note}</p> : null}
          </Card>
          <Section title={t("concierge.messages")} description={t("admin.messagesLead")} id="messages">
            <MessageThread caseId={c.id} locale={locale} viewerRole="coordinator" canPost={mine} />
          </Section>
          <Section title={t("concierge.options")} id="options">
            {options.length ? (
              <ul className="mb-4 space-y-2 text-sm">
                {options.map((o) => (
                  <li key={o.id} className="flex flex-wrap items-center gap-2">
                    <span>{o.label ?? o.provider_id}</span>
                    <StatusBadge status={o.status} kind="optionStatus" locale={locale} />
                  </li>
                ))}
              </ul>
            ) : null}
            <Card>
              <Form action={proposeOptionAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.proposeOption")} resetOnSuccess>
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField name="provider_id" label={t("fp.providerId")} required requiredLabel={t("common.required")} dir="ltr" />
                  <TextField name="service_id" label={t("admin.serviceId")} optionalLabel={t("common.optional")} dir="ltr" />
                  <TextField name="facility_id" label={t("admin.facilityId")} optionalLabel={t("common.optional")} dir="ltr" />
                  <TextField name="branch_id" label={t("pp.branchId")} optionalLabel={t("common.optional")} dir="ltr" />
                  <TextField className="sm:col-span-2" name="label" label={t("admin.optionLabel")} hint={t("admin.optionLabelHint")} optionalLabel={t("common.optional")} maxLength={200} />
                </div>
                <div className="mt-4">
                  <SubmitButton variant="secondary" pendingLabel={t("common.saving")}>{t("admin.proposeOption")}</SubmitButton>
                </div>
              </Form>
            </Card>
          </Section>
          <Section title={t("admin.notes")} description={t("admin.notesLead")} id="notes">
            <ul className="mb-4 space-y-2">
              {notes.map((n) => (
                <li key={n.id} className="rounded-md border border-border bg-surface p-3 text-sm">
                  <p className="text-xs text-text-muted hx-ltr-nums">{formatDateTime(n.created_at, locale)}</p>
                  <p className="mt-1 whitespace-pre-wrap">{n.body}</p>
                </li>
              ))}
            </ul>
            <Form action={addNoteAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.addNote")} resetOnSuccess>
              <TextArea name="body" label={t("admin.addNote")} required requiredLabel={t("common.required")} maxLength={4000} rows={3} />
              <div className="mt-3">
                <SubmitButton variant="secondary" pendingLabel={t("common.saving")}>{t("admin.addNote")}</SubmitButton>
              </div>
            </Form>
          </Section>
          <Section title={t("admin.audit")} id="audit">
            <ol className="space-y-1 text-sm">
              {audit.map((a) => (
                <li key={a.id} className="flex flex-wrap gap-2">
                  <span className="hx-ltr-nums text-text-muted">{formatDateTime(a.created_at, locale, { dateStyle: "short", timeStyle: "short" })}</span>
                  <span>{t(`admin.auditAction_${a.action}`)}</span>
                  {a.to_status ? <span>→ {t(`enums.caseStatus.${a.to_status}`)}</span> : null}
                  <span className="text-text-muted">({a.actor_role})</span>
                  {a.reason ? <span className="text-text-muted">“{a.reason}”</span> : null}
                </li>
              ))}
            </ol>
          </Section>
        </div>
        <aside className="space-y-6">
          {!c.coordinator_id || supervisor ? (
            <Card>
              <h2 className="text-lg">{t("admin.assignment")}</h2>
              <Form action={assignCaseAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.assignment")}>
                {supervisor ? <TextField name="coordinator_id" label={t("admin.coordinatorId")} hint={t("admin.coordinatorIdHint")} optionalLabel={t("common.optional")} dir="ltr" className="mt-3" /> : null}
                <div className="mt-3">
                  <SubmitButton pendingLabel={t("common.saving")}>{supervisor ? t("admin.assign") : t("admin.claim")}</SubmitButton>
                </div>
              </Form>
            </Card>
          ) : null}
          {next.length ? (
            <Card>
              <h2 className="text-lg">{t("admin.moveCase")}</h2>
              <Form action={transitionCaseAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.moveCase")}>
                <div className="mt-3 space-y-3">
                  <SelectField name="to_status" label={t("admin.newStatus")} required requiredLabel={t("common.required")} options={next.map((s) => ({ value: s, label: t(`enums.caseStatus.${s}`) }))} />
                  <TextArea name="reason" label={t("admin.reason")} optionalLabel={t("common.optional")} maxLength={500} rows={2} />
                  <SubmitButton pendingLabel={t("common.saving")}>{t("admin.applyStatus")}</SubmitButton>
                </div>
              </Form>
            </Card>
          ) : null}
          {c.status !== "escalated" && !["completed", "cancelled"].includes(c.status) ? (
            <Card>
              <h2 className="text-lg">{t("admin.escalate")}</h2>
              <Form action={escalateCaseAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.escalate")}>
                <div className="mt-3 space-y-3">
                  <TextArea name="reason" label={t("admin.reason")} required requiredLabel={t("common.required")} maxLength={500} rows={2} />
                  <SubmitButton variant="danger" pendingLabel={t("common.saving")}>{t("admin.escalate")}</SubmitButton>
                </div>
              </Form>
            </Card>
          ) : null}
        </aside>
      </div>
    </>
  );
}
