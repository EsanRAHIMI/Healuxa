import { feeBreakdown, formatMoney, minorUnitExponent } from '../format/money';

const aed = (amount_minor: number) => ({ amount_minor, currency: 'AED' });

describe('fee formatting', () => {
  it('formats AED minor units (fils) with two decimals', () => {
    const s = formatMoney(aed(60000), 'en');
    expect(s).toMatch(/600\.00/);
    expect(s).toMatch(/AED/);
  });

  it('formats Arabic with Arabic currency symbol', () => {
    const s = formatMoney(aed(60000), 'ar');
    expect(s).toMatch(/د\.إ/);
  });

  it('uses three decimals for KWD', () => {
    expect(minorUnitExponent('KWD')).toBe(3);
    expect(formatMoney({ amount_minor: 12345, currency: 'KWD' }, 'en')).toMatch(/12\.345/);
  });

  it('builds a consistent professional + facility breakdown', () => {
    const b = feeBreakdown({ price_type: 'fixed', price: aed(60000), professional_fee: aed(45000), facility_fee: aed(15000) });
    expect(b).toEqual({ priceType: 'fixed', total: aed(60000), professional: aed(45000), facility: aed(15000), consistent: true });
  });

  it('derives the total when the backend omits it', () => {
    const b = feeBreakdown({ price_type: 'from', price: null, professional_fee: aed(100), facility_fee: aed(50) });
    expect(b.total).toEqual(aed(150));
    expect(b.consistent).toBe(true);
  });

  it('flags totals that do not add up instead of hiding them', () => {
    const b = feeBreakdown({ price_type: 'fixed', price: aed(999), professional_fee: aed(100), facility_fee: aed(50) });
    expect(b.consistent).toBe(false);
    expect(b.total).toEqual(aed(999));
  });

  it('flags mixed currencies', () => {
    const b = feeBreakdown({ price_type: 'fixed', price: aed(150), professional_fee: aed(100), facility_fee: { amount_minor: 50, currency: 'USD' } });
    expect(b.consistent).toBe(false);
  });

  it('shows no amounts for on-request pricing', () => {
    const b = feeBreakdown({ price_type: 'on_request', price: null, professional_fee: null, facility_fee: null });
    expect(b).toMatchObject({ priceType: 'on_request', total: null });
  });
});
