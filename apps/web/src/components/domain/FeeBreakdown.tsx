import type { ServiceOffering } from "@healuxa/api-client";
import { formatMoney, type Locale } from "@healuxa/i18n";

import { getT } from "@/lib/i18n";

/**
 * Transparent price: professional fee + facility fee = total, exactly as provider-service computes it
 * (minor units). "from" prices are labelled as starting prices; on-request offerings show no number.
 */
export function FeeBreakdown({ offering, locale, compact = false }: { offering: ServiceOffering; locale: Locale; compact?: boolean }) {
  const t = getT(locale);
  if (offering.price_type === "on_request" || !offering.price) {
    return <p className="font-medium" data-testid="fee-on-request">{t("payment.onRequest")}</p>;
  }
  const money = (m: { amount_minor: number; currency: string } | null | undefined) =>
    m ? <span className="hx-ltr-nums">{formatMoney(m.amount_minor, m.currency, locale)}</span> : "—";
  const totalLabel = offering.price_type === "from" ? t("payment.totalFrom") : t("payment.total");
  if (compact) {
    return (
      <p className="font-semibold" data-testid="fee-total">
        {offering.price_type === "from" ? t("payment.from", { amount: formatMoney(offering.price.amount_minor, offering.price.currency, locale) }) : money(offering.price)}
      </p>
    );
  }
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm" data-testid="fee-breakdown">
      <dt className="text-text-muted">{t("payment.professionalFee")}</dt>
      <dd className="text-end" data-testid="fee-professional">{money(offering.professional_fee)}</dd>
      <dt className="text-text-muted">{t("payment.facilityFee")}</dt>
      <dd className="text-end" data-testid="fee-facility">{money(offering.facility_fee)}</dd>
      <dt className="border-t border-border pt-1 font-semibold">{totalLabel}</dt>
      <dd className="border-t border-border pt-1 text-end font-semibold" data-testid="fee-total">
        {money(offering.price)}
      </dd>
    </dl>
  );
}
