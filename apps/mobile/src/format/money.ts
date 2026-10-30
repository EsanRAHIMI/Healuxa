import type { Money, ServiceOffering } from '../api/types';

/** ISO 4217 minor-unit exponents that differ from 2 (fils for AED is 2). */
const EXPONENT: Record<string, number> = { BHD: 3, KWD: 3, OMR: 3, JOD: 3, IQD: 3, TND: 3, JPY: 0, KRW: 0 };

export const minorUnitExponent = (currency: string) => EXPONENT[currency.toUpperCase()] ?? 2;

const LOCALE_TAG: Record<string, string> = { en: 'en-AE', ar: 'ar-AE', fa: 'fa-IR' };

export function formatMoney(money: Money, language: string): string {
  const exp = minorUnitExponent(money.currency);
  const major = money.amount_minor / 10 ** exp;
  const tag = LOCALE_TAG[language] ?? language;
  try {
    return new Intl.NumberFormat(tag, {
      style: 'currency',
      currency: money.currency,
      minimumFractionDigits: exp,
      maximumFractionDigits: exp,
    }).format(major);
  } catch {
    return `${money.currency} ${major.toFixed(exp)}`;
  }
}

export interface FeeBreakdown {
  priceType: ServiceOffering['price_type'];
  total: Money | null;
  professional: Money | null;
  facility: Money | null;
  /** false if the backend total does not equal professional + facility (never hide that) */
  consistent: boolean;
}

/** Builds the transparent fee breakdown shown for an offering (provider.openapi.yaml ServiceOffering). */
export function feeBreakdown(o: Pick<ServiceOffering, 'price_type' | 'price' | 'professional_fee' | 'facility_fee'>): FeeBreakdown {
  if (o.price_type === 'on_request') {
    return { priceType: 'on_request', total: null, professional: null, facility: null, consistent: true };
  }
  const professional = o.professional_fee ?? null;
  const facility = o.facility_fee ?? null;
  let total = o.price ?? null;
  let consistent = true;
  const currency = total?.currency ?? professional?.currency ?? facility?.currency;
  const parts = [professional, facility].filter((m): m is Money => m !== null);
  if (parts.some((m) => m.currency !== currency)) consistent = false;
  const sum = parts.reduce((acc, m) => acc + m.amount_minor, 0);
  if (!total && parts.length && currency) total = { amount_minor: sum, currency };
  else if (total && parts.length && sum !== total.amount_minor) consistent = false;
  return { priceType: o.price_type, total, professional, facility, consistent };
}
