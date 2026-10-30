import { useRouter } from 'expo-router';

import { useI18n } from '../i18n';
import { AppText, Button, Card, Screen } from './primitives';

/** Shown by tabs whose content is the customer's own data (bookings, concierge). */
export function SignedOutPrompt({ intro }: { intro?: string }) {
  const { t } = useI18n();
  const router = useRouter();
  return (
    <Screen>
      {intro ? <AppText muted>{intro}</AppText> : null}
      <Card>
        <AppText>{t('common.signInRequired')}</AppText>
        <Button label={t('welcome.signIn')} onPress={() => router.push('/sign-in')} />
        <Button kind="secondary" label={t('welcome.register')} onPress={() => router.push('/register')} />
      </Card>
    </Screen>
  );
}
