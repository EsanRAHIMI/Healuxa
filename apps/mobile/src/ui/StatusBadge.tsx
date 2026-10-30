import { View } from 'react-native';

import type { AppointmentStatus, CaseStatus } from '../api/types';
import { type MessageKey, useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText } from './primitives';

const POSITIVE = new Set(['confirmed', 'checked_in', 'completed', 'arranged']);
const NEGATIVE = new Set(['cancelled', 'declined', 'no_show', 'expired']);

export function StatusBadge({ kind, status }: { kind: 'appointments' | 'concierge'; status: AppointmentStatus | CaseStatus }) {
  const { t } = useI18n();
  const theme = useTheme();
  const color = POSITIVE.has(status) ? theme.color.success : NEGATIVE.has(status) ? theme.color.danger : theme.color.accent;
  const label = t(`${kind}.status.${status}` as MessageKey);
  return (
    <View
      accessible
      accessibilityLabel={label}
      style={{ alignSelf: 'flex-start', borderRadius: theme.radius.pill, borderWidth: 1, borderColor: color, paddingHorizontal: theme.space(2), paddingVertical: 2 }}
    >
      <AppText variant="caption" style={{ color, fontWeight: '600' }}>
        {label}
      </AppText>
    </View>
  );
}
