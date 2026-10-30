import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback } from 'react';

import { useAuth } from '@/auth/AuthProvider';
import { formatDate } from '@/i18n/labels';
import { useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { useApi } from '@/services';
import { AppText, Button, EmptyState, ErrorState, Loading, PressableCard, Screen } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';
import { StatusBadge } from '@/ui/StatusBadge';

/** Concierge requests. Uses concierge: listMyConciergeCases (newest first). */
export default function Concierge() {
  const { t, language } = useI18n();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const signedIn = auth.status === 'signedIn';
  const cases = useRemote(
    () => (signedIn ? auth.withAuth((tk) => api.concierge.listMine(tk)) : Promise.resolve(null)),
    [api, signedIn, auth.withAuth]
  );
  const { reload } = cases;
  useFocusEffect(useCallback(() => reload(), [reload]));

  if (!signedIn) return <SignedOutPrompt intro={t('concierge.intro')} />;

  return (
    <Screen testID="concierge-screen" onRefresh={cases.reload} refreshing={cases.refreshing}>
      <AppText muted>{t('concierge.intro')}</AppText>
      <Button label={t('concierge.new')} icon="add-circle-outline" onPress={() => router.push('/concierge/new')} testID="concierge-new" />
      {cases.loading ? (
        <Loading />
      ) : cases.error ? (
        <ErrorState error={cases.error} onRetry={cases.reload} />
      ) : !cases.data?.data.length ? (
        <EmptyState message={t('concierge.empty')} />
      ) : (
        cases.data.data.map((c) => (
          <PressableCard
            key={c.id}
            testID={`case-${c.id}`}
            accessibilityLabel={t(`concierge.category.${c.category}` as MessageKey)}
            onPress={() => router.push({ pathname: '/concierge/[id]', params: { id: c.id } })}
          >
            <AppText variant="label">{t(`concierge.category.${c.category}` as MessageKey)}</AppText>
            <AppText variant="caption" muted>{formatDate(c.created_at, language)}</AppText>
            <StatusBadge kind="concierge" status={c.status} />
          </PressableCard>
        ))
      )}
    </Screen>
  );
}
