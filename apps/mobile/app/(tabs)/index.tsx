import { Redirect, useFocusEffect, useRouter } from 'expo-router';
import { useCallback } from 'react';

import { useAuth } from '@/auth/AuthProvider';
import { usePublic, useRemote } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { JourneyHomeCard } from '@/journey/JourneyHomeCard';
import { loadJourneySummary } from '@/journey/load';
import { usePrefs } from '@/prefs';
import { useApi } from '@/services';
import { AppText, Button, EmptyState, ErrorState, Loading, OfflineBanner, Row, Screen, Section } from '@/ui/primitives';
import { ProviderCard } from '@/ui/ProviderCard';

/**
 * Home. Uses provider: searchProviders (limit 3), notification: getUnreadNotificationCount and, for
 * the journey card, transformation: getJourneyByUser → getRoadmap + getNextActions.
 */
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

  // transformation: the signed-in customer's journey summary (never cached); null when signed out.
  const userId = auth.userId;
  const journey = useRemote(
    () => (signedIn && userId ? auth.withAuth((tk) => loadJourneySummary(api, tk, userId)) : Promise.resolve(null)),
    [api, signedIn, userId, auth.withAuth]
  );
  // Refresh when the tab regains focus (after starting a journey, the intake form or a booking).
  const reloadJourney = journey.reload;
  useFocusEffect(useCallback(() => reloadJourney(), [reloadJourney]));
  const refresh = () => {
    featured.reload();
    journey.reload();
  };

  if (!prefs.welcomeSeen && auth.status === 'signedOut') return <Redirect href="/welcome" />;

  return (
    <Screen testID="home-screen" onRefresh={refresh} refreshing={featured.refreshing}>
      <AppText variant="title">{auth.status === 'signedIn' ? t('home.greetingSignedIn') : t('home.greeting')}</AppText>
      <AppText muted>{t('home.intro')}</AppText>
      <JourneyHomeCard summary={journey} />
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
