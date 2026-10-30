/**
 * In-app account deletion (App Store 5.1.1(v), Google Play account-deletion policy).
 * identity: authDeleteAccount with password re-confirmation. On 204 the account is anonymised,
 * every session revoked and auth.user_deleted emitted so other services erase their data; the app
 * then wipes its local session. A wrong password (401) leaves the account untouched.
 */
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { ApiError } from '@/api/errors';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Screen, TextField } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

export default function DeleteAccount() {
  const { t } = useI18n();
  const theme = useTheme();
  const auth = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);

  if (auth.status !== 'signedIn') return <SignedOutPrompt />;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      await auth.deleteAccount(password);
      Alert.alert(t('delete.title'), t('delete.done'));
      router.dismissTo('/');
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' });
      setError(err.status === 401 ? 'delete.wrongPassword' : errorKey(err));
    } finally {
      setBusy(false);
    }
  };

  const confirm = () =>
    Alert.alert(t('delete.title'), t('delete.confirm'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('delete.cta'), style: 'destructive', onPress: run },
    ]);

  return (
    <Screen testID="delete-screen">
      <AppText variant="title">{t('delete.title')}</AppText>
      <Card style={{ borderColor: theme.color.danger }}>
        <AppText>{t('delete.body')}</AppText>
      </Card>
      <TextField
        label={t('delete.password')}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        secureToggle
        autoCapitalize="none"
        autoComplete="current-password"
        textContentType="password"
        testID="delete-password"
      />
      {error ? (
        <AppText accessibilityRole="alert" style={{ color: theme.color.danger }} testID="delete-error">
          {t(error)}
        </AppText>
      ) : null}
      <Button kind="danger" label={t('delete.cta')} icon="trash-outline" onPress={confirm} busy={busy} disabled={!password} testID="delete-submit" />
    </Screen>
  );
}
