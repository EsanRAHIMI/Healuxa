import { View } from 'react-native';

import type { ServiceOffering } from '../api/types';
import { feeBreakdown, formatMoney } from '../format/money';
import { useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText } from './primitives';

/** Transparent fee breakdown: total plus professional and facility parts (never hidden). */
export function FeeBreakdownView({ offering, testID }: { offering: ServiceOffering; testID?: string }) {
  const { t, language } = useI18n();
  const theme = useTheme();
  const b = feeBreakdown(offering);

  if (b.priceType === 'on_request' || !b.total) {
    return (
      <AppText testID={testID} variant="label">
        {t('fees.onRequest')}
      </AppText>
    );
  }
  const total = formatMoney(b.total, language);
  const headline = b.priceType === 'from' ? t('fees.from', { amount: total }) : total;
  const line = (label: string, value: string, id: string) => (
    <View
      testID={testID ? `${testID}-${id}` : undefined}
      accessible
      accessibilityLabel={`${label}: ${value}`}
      style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space(2) }}
    >
      <AppText variant="small" muted>
        {label}
      </AppText>
      <AppText variant="small">{value}</AppText>
    </View>
  );
  return (
    <View testID={testID} style={{ gap: theme.space(1) }}>
      <View
        accessible
        accessibilityLabel={`${t('fees.total')}: ${headline}`}
        style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space(2) }}
      >
        <AppText variant="label">{t('fees.total')}</AppText>
        <AppText variant="label" testID={testID ? `${testID}-total` : undefined}>
          {headline}
        </AppText>
      </View>
      {b.professional ? line(t('fees.professional'), formatMoney(b.professional, language), 'professional') : null}
      {b.facility ? line(t('fees.facility'), formatMoney(b.facility, language), 'facility') : null}
      {!b.consistent ? (
        <AppText variant="caption" style={{ color: theme.color.danger }} accessibilityRole="alert">
          {t('fees.inconsistent')}
        </AppText>
      ) : null}
    </View>
  );
}
