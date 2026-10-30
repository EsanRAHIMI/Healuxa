import { newIdempotencyKey, unwrap } from "@healuxa/api-client";
import { formatDateTime, formatMoney } from "@healuxa/i18n";

import { capturePaymentAction, refundAction } from "@/actions/admin";
import { StatusBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CheckboxField, SelectField, SubmitButton, TextArea, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { FilterBar, FilterInput } from "@/components/ui/filters";
import { Alert, Card, DefinitionList, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

const REASONS = ["requested_by_customer", "appointment_cancelled", "provider_declined", "duplicate", "fraudulent", "service_issue", "goodwill"] as const;

/**
 * Finance console (payment-service): look up a payment, capture/void, refund (full, partial or by
 * policy, always with a reason + note), reconciliation report and disputes.
 */
export default async function AdminPayments({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const sp = await searchParams;
  const paymentId = qp(sp, "payment_id", 40);
  const from = qp(sp, "from", 10);
  const to = qp(sp, "to", 10);
  const api = await userApi();
  const payment = paymentId && /^[A-Za-z0-9-]{10,36}$/.test(paymentId) ? await settle(async () => {
    const [p, refunds, policy] = await Promise.all([
      unwrap(api.payment.GET("/payments/{id}", { params: { path: { id: paymentId } } })),
      unwrap(api.payment.GET("/payments/{id}/refunds", { params: { path: { id: paymentId } } })).then((r) => r.data).catch(() => []),
      unwrap(api.payment.GET("/payments/{id}/refund-policy", { params: { path: { id: paymentId } } })).catch(() => null),
    ]);
    return { p, refunds, policy };
  }) : null;
  const canReconcile = hasPermission(session, "finance:reconcile");
  const recon = canReconcile && from && to ? await settle(() => unwrap(api.payment.GET("/payments/reconciliation", { params: { query: { from: `${from}T00:00:00Z`, to: `${to}T23:59:59Z` } } }))) : null;
  const disputes = hasPermission(session, "payments:manage") ? await settle(() => unwrap(api.payment.GET("/payments/disputes", { params: { query: {} } }))) : null;
  const base = `/${locale}/admin/payments`;
  const money = (minor: number, currency: string) => <span className="hx-ltr-nums">{formatMoney(minor, currency, locale)}</span>;
  return (
    <>
      <PageHeader title={t("admin.payments")} lead={t("admin.paymentsLead")} />
      <FilterBar action={base} label={t("admin.findPayment")} submitLabel={t("common.search")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterInput name="payment_id" label={t("admin.paymentId")} defaultValue={paymentId} />
      </FilterBar>
      {payment ? (
        !payment.ok ? (
          <div className="mt-6"><ServiceError error={payment.error} locale={locale} /></div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-[3fr_2fr]">
            <Card>
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-xl">{money(payment.value.p.amount.amount_minor, payment.value.p.amount.currency)}</h2>
                <StatusBadge status={payment.value.p.status} kind="paymentStatus" locale={locale} />
              </div>
              <DefinitionList
                className="mt-4"
                items={[
                  { term: t("admin.customer"), value: <span className="hx-ltr-nums text-sm">{payment.value.p.user_id}</span> },
                  { term: t("admin.subject"), value: `${t(`payments.subject_${payment.value.p.subject_type}`)} · ${payment.value.p.subject_id}` },
                  { term: t("admin.captured"), value: money(payment.value.p.amount_captured_minor ?? 0, payment.value.p.amount.currency) },
                  { term: t("admin.refunded"), value: money(payment.value.p.amount_refunded_minor ?? 0, payment.value.p.amount.currency) },
                  ...(payment.value.policy ? [{ term: t("admin.policy"), value: <>{money(payment.value.policy.refundable_minor, payment.value.p.amount.currency)} ({t(`admin.policy_${payment.value.policy.rule}`)})</> }] : []),
                ]}
              />
              {payment.value.refunds.length ? (
                <ul className="mt-4 space-y-1 text-sm">
                  {payment.value.refunds.map((r) => (
                    <li key={r.id}>
                      {money(r.amount.amount_minor, r.amount.currency)} · {r.reason} · {t(`payments.refundStatus_${r.status}`)}
                    </li>
                  ))}
                </ul>
              ) : null}
              {payment.value.p.status === "authorized" && hasPermission(session, "payments:manage") ? (
                <Form action={capturePaymentAction} locale={locale} hidden={{ payment_id: payment.value.p.id }} label={t("admin.capture")}>
                  <div className="mt-4 flex gap-2">
                    <SubmitButton name="op" value="capture" pendingLabel={t("common.saving")}>{t("admin.capture")}</SubmitButton>
                    <SubmitButton name="op" value="cancel" variant="secondary" pendingLabel={t("common.saving")}>{t("admin.void")}</SubmitButton>
                  </div>
                </Form>
              ) : null}
            </Card>
            {hasPermission(session, "payments:refund") && ["succeeded", "partially_refunded"].includes(payment.value.p.status) ? (
              <Card>
                <h2 className="text-lg">{t("admin.refund")}</h2>
                <Form action={refundAction} locale={locale} hidden={{ payment_id: payment.value.p.id, idempotency_key: newIdempotencyKey("refund") }} label={t("admin.refund")}>
                  <div className="mt-3 space-y-4">
                    <SelectField name="reason" label={t("admin.reason")} required requiredLabel={t("common.required")} options={REASONS.map((r) => ({ value: r, label: t(`admin.refundReason_${r}`) }))} />
                    <TextField name="amount" label={t("admin.refundAmount")} hint={t("admin.refundAmountHint")} optionalLabel={t("common.optional")} inputMode="decimal" dir="ltr" />
                    <CheckboxField name="apply_policy" label={t("admin.applyPolicy")} />
                    <TextArea name="note" label={t("admin.note")} required requiredLabel={t("common.required")} maxLength={500} rows={2} />
                    <SubmitButton variant="danger" pendingLabel={t("common.saving")}>{t("admin.refund")}</SubmitButton>
                  </div>
                </Form>
              </Card>
            ) : null}
          </div>
        )
      ) : null}
      {canReconcile ? (
        <Section title={t("admin.reconciliation")} description={t("admin.reconciliationLead")} id="reconciliation">
          <form method="get" action={base} className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              {t("admin.from")}
              <input type="date" name="from" defaultValue={from} required className="mt-1 block min-h-11 rounded-md border border-border-strong bg-surface px-2" />
            </label>
            <label className="text-sm">
              {t("admin.to")}
              <input type="date" name="to" defaultValue={to} required className="mt-1 block min-h-11 rounded-md border border-border-strong bg-surface px-2" />
            </label>
            <button type="submit" className="min-h-11 rounded-md bg-primary px-4 text-on-primary">{t("admin.runReport")}</button>
          </form>
          {recon ? (
            !recon.ok ? (
              <div className="mt-4"><ServiceError error={recon.error} locale={locale} /></div>
            ) : (
              <div className="mt-4 space-y-3">
                <p>{t("admin.matched", { count: recon.value.matched })}</p>
                {recon.value.mismatches.length === 0 ? (
                  <Alert tone="success" role="status" title={t("admin.noMismatches")} />
                ) : (
                  <ul className="space-y-1 text-sm" data-testid="mismatches">
                    {recon.value.mismatches.map((m, i) => (
                      <li key={i} className="rounded-md border border-warning bg-warning-soft p-2 text-on-warning-soft">
                        {m.kind} · {m.payment_id ?? m.processor_ref ?? "—"}
                        {m.expected_minor != null ? ` · ${m.expected_minor} → ${m.actual_minor ?? "—"}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          ) : null}
        </Section>
      ) : null}
      {disputes ? (
        <Section title={t("admin.disputes")} id="disputes">
          {!disputes.ok ? (
            <ServiceError error={disputes.error} locale={locale} />
          ) : disputes.value.data.length === 0 ? (
            <EmptyState title={t("admin.noDisputes")} />
          ) : (
            <ul className="space-y-2 text-sm">
              {disputes.value.data.map((d) => (
                <li key={d.id} className="flex flex-wrap gap-2">
                  {money(d.amount.amount_minor, d.amount.currency)} · {d.status} · {d.payment_id}
                  {d.evidence_due_by ? <span className="text-danger">{t("admin.evidenceDue", { date: formatDateTime(d.evidence_due_by, locale) })}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}
    </>
  );
}
