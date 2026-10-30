import { Stack, useRouter } from 'expo-router';

import { useI18n } from '@/i18n';
import { AppText, Button, Screen } from '@/ui/primitives';

export default function NotFound() {
  const { t } = useI18n();
  const router = useRouter();
  return (
    <Screen testID="not-found-screen">
      <Stack.Screen options={{ title: '' }} />
      <AppText variant="heading">{t('error.notFound')}</AppText>
      <Button label={t('tabs.home')} onPress={() => router.replace('/')} />
    </Screen>
  );
}
