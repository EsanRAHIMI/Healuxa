import { Redirect } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking } from 'react-native';

import { useAuth } from '@/auth/AuthProvider';
import { config } from '@/config';
import { useI18n } from '@/i18n';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Screen } from '@/ui/primitives';

/**
 * Account deletion entry point (App Store 5.1.1(v) / Google Play account-deletion policy).
 *
 * identity-service has NO account-deletion endpoint yet, so this screen explains how deletion is
 * requested and opens a pre-filled email to support. It never claims the account was deleted.
 */
export default function DeleteAccount() {
  const { t } = useI18n();
  const theme = useTheme();
  const auth = useAuth();
  const [opening, setOpening] = useState(false);

  if (auth.status !== 'signedIn') return <Redirect href="/account" />;

  const email = config.supportEmail;
  const request = async () => {
    setOpening(true);
    const url = `mailto:${email}?subject=${encodeURIComponent(t('delete.subject'))}&body=${encodeURIComponent(
      t('delete.mailBody', { id: auth.userId ?? '' })
    )}`;
    try {
      if (await Linking.canOpenURL(url)) await Linking.openURL(url);
      else Alert.alert(t('delete.title'), t('delete.noMail', { email }));
    } catch {
      Alert.alert(t('delete.title'), t('delete.noMail', { email }));
    } finally {
      setOpening(false);
    }
  };

  return (
    <Screen testID="delete-screen">
      <AppText variant="title">{t('delete.title')}</AppText>
      <AppText>{t('delete.body')}</AppText>
      <Card>
        <AppText>{t('delete.how')}</AppText>
        <AppText variant="small" selectable muted>
          {email}
        </AppText>
      </Card>
      <Card accessibilityRole="summary" testID="delete-status" style={{ borderColor: theme.color.danger }}>
        <AppText variant="label">{t('delete.notDeletedYet')}</AppText>
      </Card>
      <Button kind="danger" label={t('delete.cta')} icon="mail-outline" onPress={request} busy={opening} testID="delete-request" />
    </Screen>
  );
}
