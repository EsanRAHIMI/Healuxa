import { render, screen } from '@testing-library/react-native';
import { I18nManager } from 'react-native';

import { ar } from '../i18n/ar';
import { en } from '../i18n/en';
import { fa } from '../i18n/fa';
import { applyDirection, I18nProvider, isRTLLanguage, translate } from '../i18n';
import { FeeBreakdownView } from '../ui/FeeBreakdownView';
import { AppText } from '../ui/primitives';

const offering = {
  id: 'O1',
  provider_id: 'P1',
  branch_id: 'B1',
  category: 'dermatology',
  name: 'Consultation',
  duration_minutes: 30,
  price_type: 'fixed' as const,
  status: 'active' as const,
  price: { amount_minor: 60000, currency: 'AED' },
  professional_fee: { amount_minor: 45000, currency: 'AED' },
  facility_fee: { amount_minor: 15000, currency: 'AED' },
};

function fakeManager(isRTL: boolean) {
  return { isRTL, allowRTL: jest.fn(), forceRTL: jest.fn() };
}

describe('RTL layout', () => {
  it('marks Arabic and Persian as right-to-left', async () => {
    expect(isRTLLanguage('ar')).toBe(true);
    expect(isRTLLanguage('fa')).toBe(true);
    expect(isRTLLanguage('en')).toBe(false);
  });

  it('forces RTL and asks for a restart when switching to Arabic from LTR', async () => {
    const m = fakeManager(false);
    expect(applyDirection('ar', m)).toBe(true);
    expect(m.allowRTL).toHaveBeenCalledWith(true);
    expect(m.forceRTL).toHaveBeenCalledWith(true);
  });

  it('does not need a restart when the direction already matches', async () => {
    const m = fakeManager(true);
    expect(applyDirection('fa', m)).toBe(false);
    expect(m.forceRTL).not.toHaveBeenCalled();
  });

  it('switches back to LTR for English', async () => {
    const m = fakeManager(true);
    expect(applyDirection('en', m)).toBe(true);
    expect(m.forceRTL).toHaveBeenCalledWith(false);
  });

  it('every catalog has the same keys as English', async () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort());
    expect(Object.keys(fa).sort()).toEqual(Object.keys(en).sort());
  });

  it('interpolates parameters', async () => {
    expect(translate('en', 'fees.from', { amount: 'AED 1.00' })).toBe('From AED 1.00');
    expect(translate('ar', 'fees.from', { amount: 'X' })).toBe('ابتداءً من X');
  });

  it('renders the fee breakdown in Arabic', async () => {
    await render(
      <I18nProvider initialLanguage="ar">
        <FeeBreakdownView offering={offering} testID="fees" />
      </I18nProvider>
    );
    expect(screen.getByText(ar['fees.total'])).toBeTruthy();
    expect(screen.getByText(ar['fees.professional'])).toBeTruthy();
    expect(screen.getByText(ar['fees.facility'])).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(`^${ar['fees.professional']}: `))).toBeTruthy();
  });

  it('text follows the native layout direction', async () => {
    const original = I18nManager.isRTL;
    Object.defineProperty(I18nManager, 'isRTL', { value: true, configurable: true });
    try {
      await render(<AppText testID="t">مرحبا</AppText>);
      const style = [screen.getByTestId('t').props.style].flat(3).reduce((a, s) => ({ ...a, ...s }), {});
      expect(style.writingDirection).toBe('rtl');
      expect(style.textAlign).toBe('auto');
    } finally {
      Object.defineProperty(I18nManager, 'isRTL', { value: original, configurable: true });
    }
  });
});
