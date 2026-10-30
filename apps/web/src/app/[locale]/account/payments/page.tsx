import { unwrap } from "@healuxa/api-client";
import { formatDate, formatMoney } from "@healuxa/i18n";
import Link from "next/link";

import { StatusBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

/** Customer payments and tax invoices / credit notes (payment-service). */
export default async function MyPayments({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const [payments, invoices] = await Promise.all([
    settle(() => unwrap(api.payment.GET("/payments", { params: { query: {} } }))),
    settle(() => unwrap(api.payment.GET("/invoices", { params: { query: {} } }))),
  ]);
  return (
    <>
      <PageHeader title={t("payments.title")} lead={t("payments.lead")} />
      <Section title={t("payments.payments")} id="payments">
        {!payments.ok ? (
          <ServiceError error={payments.error} locale={locale} />
        ) : payments.value.data.length === 0 ? (
          <EmptyState title={t("payments.empty")} />
        ) : (
          <ul className="space-y-3" data-testid="payments">
            {payments.value.data.map((p) => (
              <Card as="li" key={p.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <Link href={`/${locale}/account/payments/${p.id}`} className="font-medium hx-ltr-nums">
                    {formatMoney(p.amount.amount_minor, p.amount.currency, locale)}
                  </Link>
                  <p className="text-sm text-text-muted">
                    {t(`payments.subject_${p.subject_type}`)}
                    {p.created_at ? ` · ${formatDate(p.created_at, locale)}` : ""}
                  </p>
                </div>
                <StatusBadge status={p.status} kind="paymentStatus" locale={locale} />
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("payments.invoices")} description={t("payments.invoicesLead")} id="invoices">
        {!invoices.ok ? (
          <ServiceError error={invoices.error} locale={locale} />
        ) : invoices.value.data.length === 0 ? (
          <EmptyState title={t("payments.noInvoices")} />
        ) : (
          <ul className="space-y-3">
            {invoices.value.data.map((inv) => (
              <Card as="li" key={inv.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium">
                    {t(`payments.kind_${inv.kind}`)} <span className="hx-ltr-nums">{inv.number}</span>
                  </p>
                  <p className="text-sm text-text-muted">
                    <span className="hx-ltr-nums">{formatMoney(inv.total.amount_minor, inv.total.currency, locale)}</span>
                    {inv.issued_at ? ` · ${formatDate(inv.issued_at, locale)}` : ""}
                  </p>
                </div>
                <a href={`/api/invoices/${inv.id}`} target="_blank" rel="noopener">
                  {t("payments.viewInvoice")}
                  <span className="sr-only"> {t("a11y.externalLink")}</span>
                </a>
              </Card>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}
