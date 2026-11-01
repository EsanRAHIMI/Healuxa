import { Linking } from 'react-native';

import { config } from '@/config';
import { useI18n } from '@/i18n';
import { Button } from '@/ui/primitives';

/** Content Rights: lets rights holders report a published profile; opens a pre-filled support e-mail. */
export function ReportContent({ kind, id }: { kind: 'provider' | 'facility'; id: string }) {
  const { t } = useI18n();
  const subject = encodeURIComponent(`Content report (${kind})`);
  const body = encodeURIComponent(`${kind}: ${id}\n\nReason:\n`);
  return (
    <Button
      kind="secondary"
      icon="flag-outline"
      label={t('rights.report')}
      testID={`report-${kind}`}
      onPress={() => Linking.openURL(`mailto:${config.supportEmail}?subject=${subject}&body=${body}`)}
    />
  );
}
