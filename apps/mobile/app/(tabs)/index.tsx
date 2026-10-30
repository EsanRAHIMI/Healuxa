import { Redirect, useRouter } from 'expo-router';

import { useAuth } from '@/auth/AuthProvider';
import { usePublic, useRemote } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { usePrefs } from '@/prefs';
import { useApi } from '@/services';
import { AppText, Button, EmptyState, ErrorState, Loading, OfflineBanner, Row, Screen, Section } from '@/ui/primitives';
import { ProviderCard } from '@/ui/ProviderCard';

/** Home. Uses provider: searchProviders (limit 3) and notification: getUnreadNotificationCount. */
export default function Home() {
  const { t } = useI18n();
  const router = useRouter();
  const api = useApi();
  const auth = useAuth();
  const { prefs } = usePrefs();
  const featured = usePublic(() => api.directory.searchProviders({ limit: 3 }), [api]);
  const signedIn = auth.status === 'signedIn';
  // notification: getUnreadNotificationCount (signed-in only, never cached)
  const unread = useRemote(
    () => (signedIn ? auth.withAuth((tk) => api.notifications.unreadCount(tk)) : Promise.resolve(null)),
    [api, signedIn, auth.withAuth]
  );

  if (!prefs.welcomeSeen && auth.status === 'signedOut') return <Redirect href="/welcome" />;

  return (
    <Screen testID="home-screen" onRefresh={featured.reload} refreshing={featured.refreshing}>
      <AppText variant="title">{auth.status === 'signedIn' ? t('home.greetingSignedIn') : t('home.greeting')}</AppText>
      <AppText muted>{t('home.intro')}</AppText>
      {signedIn ? (
        <Button
          kind="secondary"
          icon="notifications-outline"
          label={unread.data?.unread ? `${t('inbox.title')} · ${t('inbox.unread', { n: unread.data.unread })}` : t('inbox.title')}
          onPress={() => router.push('/notifications')}
          testID="home-inbox"
        />
      ) : null}
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
      <Button kind="secondary" label={t('home.services')} icon="pricetags-outline" onPress={() => router.push('/services')} />
      <Button kind="secondary" label={t('concierge.new')} icon="chatbubbles-outline" onPress={() => router.push(signedIn ? '/concierge/new' : '/sign-in')} />
    </Screen>
  );
}
