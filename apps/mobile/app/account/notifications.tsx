import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking } from 'react-native';

import { useI18n } from '@/i18n';
import { currentPermission, type PushPermission, pushEnabled, setUpPush } from '@/notifications/push';
import { AppText, Button, Card, Screen } from '@/ui/primitives';

/** Notification opt-in behind FEATURE_PUSH. The token is obtained but NOT registered (backend pending). */
export default function NotificationsScreen() {
  const { t } = useI18n();
  const [permission, setPermission] = useState<PushPermission | null>(null);
  const [tokenReady, setTokenReady] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (pushEnabled()) currentPermission().then(setPermission).catch(() => setPermission('undetermined'));
  }, []);

  if (!pushEnabled()) return <Redirect href="/account" />;

  const enable = async () => {
    setBusy(true);
    try {
      const r = await setUpPush();
      setPermission(r.permission);
      setTokenReady(Boolean(r.deviceToken));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="notifications-screen">
      <Card>
        <AppText>{t('notifications.body')}</AppText>
        {permission === 'granted' ? (
          <AppText variant="small">{t('notifications.granted')}</AppText>
        ) : permission === 'denied' ? (
          <>
            <AppText variant="small">{t('notifications.denied')}</AppText>
            <Button kind="secondary" label={t('common.continue')} onPress={() => Linking.openSettings()} />
          </>
        ) : (
          <Button label={t('notifications.enable')} onPress={enable} busy={busy} testID="notifications-enable" />
        )}
        {permission === 'granted' || tokenReady ? <AppText variant="small" muted>{t('notifications.pendingBackend')}</AppText> : null}
      </Card>
    </Screen>
  );
}
