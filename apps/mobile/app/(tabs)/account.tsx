import { Ionicons } from '@expo/vector-icons';
import { type Href, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking, Pressable, View } from 'react-native';

import { useAuth } from '@/auth/AuthProvider';
import { config } from '@/config';
import { type MessageKey, useI18n } from '@/i18n';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Chevron, Screen } from '@/ui/primitives';

type IconName = keyof typeof Ionicons.glyphMap;

function Item({ icon, label, onPress, testID, danger }: { icon: IconName; label: string; onPress: () => void; testID?: string; danger?: boolean }) {
  const theme = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space(3),
        minHeight: 52,
        paddingVertical: theme.space(2),
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Ionicons name={icon} size={22} color={danger ? theme.color.danger : theme.color.accent} />
      <AppText style={{ flex: 1, color: danger ? theme.color.danger : theme.color.text }}>{label}</AppText>
      <Chevron />
    </Pressable>
  );
}

/** Account. Identity data comes from the session (identity: authLogin/authRegister claims). */
export default function Account() {
  const { t } = useI18n();
  const theme = useTheme();
  const router = useRouter();
  const auth = useAuth();
  const [busy, setBusy] = useState(false);
  const signedIn = auth.status === 'signedIn';

  const go = (href: Href) => () => router.push(href);
  const item = (icon: IconName, key: MessageKey, href: Href, testID: string, danger?: boolean) => (
    <Item icon={icon} label={t(key)} onPress={go(href)} testID={testID} danger={danger} />
  );

  const signOut = async () => {
    setBusy(true);
    try {
      const confirmed = await auth.signOut();
      if (!confirmed) Alert.alert(t('account.signOut'), t('account.signOutRemoteFailed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="account-screen">
      {signedIn ? (
        <Card testID="account-identity">
          <AppText variant="caption" muted>
            {t('account.signedInAs')}
          </AppText>
          <AppText variant="label" testID="account-identifier" selectable>
            {auth.session?.identifier}
          </AppText>
          {auth.userId ? (
            <AppText variant="caption" muted selectable>
              {t('account.accountId')}: {auth.userId}
            </AppText>
          ) : null}
          <AppText variant="caption" muted>
            {t('account.profilePending')}
          </AppText>
        </Card>
      ) : (
        <Card>
          {auth.expired ? <AppText style={{ color: theme.color.danger }}>{t('error.unauthorized')}</AppText> : null}
          <AppText>{t('account.signedOutBody')}</AppText>
          <Button label={t('welcome.signIn')} onPress={go('/sign-in')} testID="account-sign-in" />
          <Button kind="secondary" label={t('welcome.register')} onPress={go('/register')} testID="account-register" />
        </Card>
      )}

      <Card>
        {signedIn ? item('phone-portrait-outline', 'account.sessions', '/account/sessions', 'account-sessions') : null}
        {item('language-outline', 'account.language', '/account/language', 'account-language')}
        {signedIn ? item('finger-print-outline', 'account.security', '/account/security', 'account-security') : null}
        {config.features.push ? item('notifications-outline', 'account.notifications', '/account/notifications', 'account-notifications') : null}
        <Item icon="document-text-outline" label={t('account.privacy')} onPress={() => Linking.openURL(config.privacyPolicyUrl)} />
        {signedIn ? item('trash-outline', 'account.delete', '/account/delete', 'account-delete', true) : null}
      </Card>

      {signedIn ? (
        <View>
          <Button kind="danger" label={t('account.signOut')} onPress={signOut} busy={busy} testID="account-sign-out" icon="log-out-outline" />
        </View>
      ) : null}
    </Screen>
  );
}
