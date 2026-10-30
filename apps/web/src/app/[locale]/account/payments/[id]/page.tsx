import { NotFoundError, unwrap } from "@healuxa/api-client";
import { formatDateTime, formatMoney } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { refreshPaymentAction } from "@/actions/booking";
import { StatusBadge } from "@/components/domain/badges";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { StripeConfirm } from "@/components/payments/StripeConfirm";
import { Alert, Card, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { env } from "@/lib/env";
import { getT, resolveLocale } from "@/lib/i18n";

const SETTLED = ["succeeded", "authorized", "failed", "canceled", "refunded", "partially_refunded"];

/**
 * Payment detail + confirmation. Status shown is payment-service's (webhook/processor verified);
 * returning from Stripe triggers a server-side refresh, never a client-declared success.
 */
export default async function PaymentDetail({ params, searchParams }: { params: Promise<{ locale: string; id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  await requireSession(locale);
  const t = getT(locale);
  const sp = await searchParams;
  const api = await userApi();
  const load = () => unwrap(api.payment.GET("/payments/{id}", { params: { path: { id } } }));
  let payment = await load().catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  if (sp.redirect_status && !SETTLED.includes(payment.status)) {
    payment = await unwrap(api.payment.POST("/payments/{id}/refresh", { params: { path: { id } } })).catch(() => payment);
  }
  const [config, refunds] = await Promise.all([
    unwrap(api.payment.GET("/payments/config")).catch(() => null),
    unwrap(api.payment.GET("/payments/{id}/refunds", { params: { path: { id } } })).then((r) => r.data).catch(() => []),
  ]);
  const money = (minor: number) => <span className="hx-ltr-nums">{formatMoney(minor, payment.amount.currency, locale)}</span>;
  const canConfirm = payment.status === "pending" && !!payment.client_secret && config?.gateway === "stripe" && !!config.publishable_key;
  return (
    <>
      <PageHeader title={t("payments.payment")} lead={t(`payments.subject_${payment.subject_type}`)} actions={<StatusBadge status={payment.status} kind="paymentStatus" locale={locale} />} />
      {config && !config.live_mode ? <Alert tone="warning" role="note" className="mb-6" title={t("payments.testMode")} /> : null}
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <Card>
            <h2 className="text-lg">{t("payments.breakdown")}</h2>
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="text-text-muted">
                  <th scope="col" className="py-1 text-start font-normal">{t("payments.item")}</th>
                  <th scope="col" className="py-1 text-end font-normal">{t("payments.net")}</th>
                  <th scope="col" className="py-1 text-end font-normal">{t("payments.vat")}</th>
                  <th scope="col" className="py-1 text-end font-normal">{t("payment.total")}</th>
                </tr>
              </thead>
              <tbody>
                {(payment.lines ?? []).map((l, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1.5">{l.description}</td>
                    <td className="py-1.5 text-end">{money(l.net_minor)}</td>
                    <td className="py-1.5 text-end">{money(l.vat_minor)}</td>
                    <td className="py-1.5 text-end">{money(l.gross_minor)}</td>
                  </tr>
                ))}
                <tr className="border-t border-border font-semibold">
                  <td className="py-1.5" colSpan={3}>{t("payment.total")}</td>
                  <td className="py-1.5 text-end" data-testid="payment-total">{money(payment.amount.amount_minor)}</td>
                </tr>
              </tbody>
            </table>
            {config?.tax.status === "pending_accountant_review" ? <p className="mt-3 text-xs text-text-muted">{t("payment.taxPendingReview")}</p> : null}
          </Card>
          {canConfirm ? (
            <Section title={t("payments.confirm")} description={t("payments.confirmLead")} id="confirm">
              <Card>
                <StripeConfirm
                  publishableKey={config!.publishable_key!}
                  clientSecret={payment.client_secret!}
                  returnUrl={`${env.siteUrl}/${locale}/account/payments/${payment.id}`}
                  locale={locale}
                  labels={{ pay: t("payments.payAmount", { amount: formatMoney(payment.amount.amount_minor, payment.amount.currency, locale) }), processing: t("payments.processing"), error: t("payments.confirmError"), loading: t("common.loading") }}
                />
              </Card>
            </Section>
          ) : null}
          {refunds.length ? (
            <Section title={t("payments.refunds")} id="refunds">
              <ul className="space-y-2 text-sm">
                {refunds.map((r) => (
                  <li key={r.id} className="flex flex-wrap gap-2">
                    {money(r.amount.amount_minor)} · {t(`payments.refundStatus_${r.status}`)}
                    {r.created_at ? <span className="text-text-muted">· {formatDateTime(r.created_at, locale)}</span> : null}
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>
        <Card className="h-fit space-y-3">
          <p className="text-sm">{t("payments.statusExplainer")}</p>
          {!SETTLED.includes(payment.status) ? (
            <Form action={refreshPaymentAction} locale={locale} hidden={{ payment_id: payment.id }} label={t("payments.checkStatus")}>
              <SubmitButton variant="secondary" pendingLabel={t("common.loading")}>{t("payments.checkStatus")}</SubmitButton>
            </Form>
          ) : null}
          {payment.invoice_id ? (
            <a href={`/api/invoices/${payment.invoice_id}`} target="_blank" rel="noopener" className="block">
              {t("payments.viewInvoice")}
            </a>
          ) : null}
          {payment.subject_type === "appointment" ? <Link href={`/${locale}/account/bookings/${payment.subject_id}`} className="block">{t("payments.viewBooking")}</Link> : null}
          {payment.failure_code ? <p className="text-sm text-danger">{t("payments.failed", { code: payment.failure_code })}</p> : null}
        </Card>
      </div>
    </>
  );
}
