import { useRouter } from 'expo-router';
import { Image, View } from 'react-native';

import { useI18n } from '@/i18n';
import { usePrefs } from '@/prefs';
import { useTheme } from '@/theme';
import { AppText, Button, Screen } from '@/ui/primitives';

export default function Welcome() {
  const { t } = useI18n();
  const theme = useTheme();
  const router = useRouter();
  const { update } = usePrefs();
  const go = async (path: '/directory' | '/sign-in' | '/register') => {
    await update({ welcomeSeen: true });
    if (path === '/directory') router.replace('/directory');
    else {
      router.replace('/');
      router.push(path);
    }
  };
  return (
    <Screen scroll={false} edges={['top', 'bottom']} testID="welcome-screen">
      <View style={{ flex: 1, justifyContent: 'center', gap: theme.space(4) }}>
        <Image
          source={require('../assets/splash-icon.png')}
          style={{ width: 72, height: 72 }}
          accessibilityIgnoresInvertColors
          accessible
          accessibilityLabel={t('app.name')}
        />
        <AppText variant="title">{t('welcome.title')}</AppText>
        <AppText muted>{t('welcome.subtitle')}</AppText>
      </View>
      <View style={{ gap: theme.space(3) }}>
        <Button label={t('welcome.browse')} onPress={() => go('/directory')} testID="welcome-browse" icon="search-outline" />
        <Button kind="secondary" label={t('welcome.register')} onPress={() => go('/register')} testID="welcome-register" />
        <Button kind="link" label={t('welcome.signIn')} onPress={() => go('/sign-in')} testID="welcome-sign-in" />
      </View>
    </Screen>
  );
}
