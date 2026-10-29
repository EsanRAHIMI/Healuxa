import { Redirect, useRouter } from 'expo-router';

import { useAuth } from '@/auth/AuthProvider';
import { usePublic } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { usePrefs } from '@/prefs';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, EmptyState, ErrorState, Loading, OfflineBanner, Row, Screen, Section } from '@/ui/primitives';
import { ProviderCard } from '@/ui/ProviderCard';

/** Home. Uses provider: searchProviders (limit 3). */
export default function Home() {
  const { t } = useI18n();
  const theme = useTheme();
  const router = useRouter();
  const api = useApi();
  const auth = useAuth();
  const { prefs } = usePrefs();
  const featured = usePublic(() => api.directory.searchProviders({ limit: 3 }), [api]);

  if (!prefs.welcomeSeen && auth.status === 'signedOut') return <Redirect href="/welcome" />;

  return (
    <Screen testID="home-screen" onRefresh={featured.reload} refreshing={featured.refreshing}>
      <AppText variant="title">{auth.status === 'signedIn' ? t('home.greetingSignedIn') : t('home.greeting')}</AppText>
      <AppText muted>{t('home.intro')}</AppText>
      {featured.fromCache ? <OfflineBanner storedAt={featured.storedAt} /> : null}
      <Section title={t('home.featured')}>
        {featured.loading ? (
          <Loading />
        ) : featured.error && !featured.data ? (
          <ErrorState error={featured.error} onRetry={featured.reload} />
        ) : featured.data?.data.length ? (
          featured.data.data.map((p) => <ProviderCard key={p.id} provider={p} />)
        ) : (
          <EmptyState message={t('directory.empty')} />
        )}
        <Row style={{ justifyContent: 'flex-end' }}>
          <Button kind="link" label={t('home.seeAll')} onPress={() => router.navigate('/directory')} testID="home-see-all" />
        </Row>
      </Section>
      <Button kind="secondary" label={t('home.services')} icon="pricetags-outline" onPress={() => router.navigate('/services')} />
      <Card style={{ backgroundColor: theme.color.surfaceAlt }}>
        <AppText variant="small" muted>
          {t('home.bookingPending')}
        </AppText>
      </Card>
    </Screen>
  );
}
