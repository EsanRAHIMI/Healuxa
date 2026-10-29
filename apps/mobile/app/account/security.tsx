import { useEffect, useState } from 'react';
import { Switch, View } from 'react-native';

import { useAuth } from '@/auth/AuthProvider';
import { useI18n } from '@/i18n';
import { biometrics } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Card, Screen } from '@/ui/primitives';

/** Optional biometric unlock gating the stored session (expo-local-authentication). */
export default function Security() {
  const { t } = useI18n();
  const theme = useTheme();
  const auth = useAuth();
  const [available, setAvailable] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    biometrics.isAvailable().then(setAvailable).catch(() => setAvailable(false));
  }, []);

  const toggle = async (next: boolean) => {
    setBusy(true);
    try {
      await auth.setBiometricLock(next, t('security.prompt'), t('common.cancel'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="security-screen">
      <Card>
        <AppText>{t('security.body')}</AppText>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: theme.space(3), minHeight: 52 }}>
          <AppText variant="label" style={{ flex: 1 }}>{t('security.toggle')}</AppText>
          <Switch
            testID="security-toggle"
            accessibilityLabel={t('security.toggle')}
            value={auth.biometricLock}
            onValueChange={toggle}
            disabled={busy || available === false}
            trackColor={{ true: theme.color.accent }}
          />
        </View>
        {available === false ? <AppText variant="small" muted>{t('security.unavailable')}</AppText> : null}
      </Card>
    </Screen>
  );
}
