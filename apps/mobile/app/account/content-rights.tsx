import { Stack } from 'expo-router';
import { Linking } from 'react-native';

import { config } from '@/config';
import { type MessageKey, useI18n } from '@/i18n';
import { AppText, Button, Card, Screen } from '@/ui/primitives';

const SECTIONS = ['source', 'licence', 'verification', 'ownership', 'removal'] as const;

/**
 * Content Rights (App Store requirement): explains that practitioner and facility content is
 * submitted by its owners under a recorded publication licence (enforced in provider-service:
 * profiles are public only with accept_content_license on record) and how to report content.
 */
export default function ContentRightsScreen() {
  const { t } = useI18n();
  return (
    <Screen testID="content-rights-screen">
      <Stack.Screen options={{ title: t('rights.title') }} />
      <AppText muted>{t('rights.lead')}</AppText>
      {SECTIONS.map((s) => (
        <Card key={s}>
          <AppText variant="label" accessibilityRole="header">
            {t(`rights.${s}.title` as MessageKey)}
          </AppText>
          <AppText>{t(`rights.${s}.body` as MessageKey)}</AppText>
        </Card>
      ))}
      <Button
        kind="secondary"
        icon="mail-outline"
        label={t('rights.contact')}
        onPress={() => Linking.openURL(`mailto:${config.supportEmail}?subject=${encodeURIComponent('Content rights request')}`)}
        testID="content-rights-contact"
      />
    </Screen>
  );
}
