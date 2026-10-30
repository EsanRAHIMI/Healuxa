import { Ionicons } from '@expo/vector-icons';
import { useCallback, useEffect, useState } from 'react';
import { View } from 'react-native';

import { useAuth } from '../auth/AuthProvider';
import { useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText, Button, Screen } from './primitives';

/** Shown instead of the app while biometric unlock is required. No session data is loaded yet. */
export function LockScreen() {
  const { t } = useI18n();
  const theme = useTheme();
  const auth = useAuth();
  const [busy, setBusy] = useState(false);

  const unlock = useCallback(async () => {
    setBusy(true);
    try {
      await auth.unlock(t('security.prompt'), t('common.cancel'));
    } finally {
      setBusy(false);
    }
  }, [auth, t]);

  // Prompt once when the lock screen appears.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    unlock();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Screen scroll={false} edges={['top', 'bottom']} testID="lock-screen">
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: theme.space(4) }}>
        <Ionicons name="lock-closed-outline" size={40} color={theme.color.accent} />
        <AppText variant="heading">{t('lock.title')}</AppText>
      </View>
      <Button label={t('lock.unlock')} onPress={unlock} busy={busy} icon="finger-print-outline" testID="lock-unlock" />
      <Button kind="link" label={t('lock.signOut')} onPress={() => auth.signOut()} />
    </Screen>
  );
}
