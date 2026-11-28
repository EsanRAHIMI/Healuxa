import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { ScrollView } from 'react-native';

import { usePublic } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Chip, EmptyState, ErrorState, Loading, OfflineBanner, Screen } from '@/ui/primitives';
import { OfferingCard } from '@/ui/OfferingCard';

/**
 * Services catalog. Uses provider: listServices (all, then filtered by category).
 *
 * Optional route params, set when the list is opened from a journey step:
 *   category     start filtered to the step's service category
 *   milestoneId  carried to the booking screen so the appointment is linked to the step
 * Without them the screen behaves exactly as the plain catalog.
 */
export default function Services() {
  const { t } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const router = useRouter();
  const params = useLocalSearchParams<{ category?: string; milestoneId?: string }>();
  const milestoneId = params.milestoneId || undefined;
  const [category, setCategory] = useState<string | undefined>(params.category || undefined);
  const all = usePublic(() => api.directory.listServices({ limit: 100 }), [api]);
  const filtered = usePublic(
    () => (category ? api.directory.listServices({ category, limit: 100 }) : Promise.resolve({ data: { data: [], page: { limit: 0, has_more: false } }, fromCache: false })),
    [api, category]
  );
  const categories = useMemo(
    // A journey category with no published services yet still gets its (selected) chip.
    () => Array.from(new Set([...(all.data?.data ?? []).map((s) => s.category), ...(params.category ? [params.category] : [])])).sort(),
    [all.data, params.category]
  );
  const shown = category ? filtered : all;

  return (
    <Screen testID="services-screen" onRefresh={shown.reload} refreshing={shown.refreshing}>
      {milestoneId ? (
        <Card testID="services-journey-banner">
          <AppText variant="small">{t('journey.booking.banner')}</AppText>
        </Card>
      ) : null}
      <AppText muted>{t('fees.disclaimer')}</AppText>
      {categories.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: theme.space(2) }}>
          <Chip label={t('services.allCategories')} selected={!category} onPress={() => setCategory(undefined)} />
          {categories.map((c) => (
            <Chip key={c} label={c} selected={category === c} onPress={() => setCategory(c)} testID={`category-${c}`} />
          ))}
        </ScrollView>
      ) : null}
      {shown.fromCache ? <OfflineBanner storedAt={shown.storedAt} /> : null}
      {shown.loading ? (
        <Loading />
      ) : shown.error && !shown.data ? (
        <ErrorState error={shown.error} onRetry={shown.reload} />
      ) : shown.data?.data.length ? (
        shown.data.data.map((s) => <OfferingCard key={s.id} offering={s} showProviderLink milestoneId={milestoneId} />)
      ) : (
        <EmptyState
          message={t('services.empty')}
          action={
            // From a journey step, the concierge is the honest alternative when nothing is published yet.
            milestoneId ? (
              <Button kind="secondary" label={t('journey.action.concierge')} icon="chatbubbles-outline" onPress={() => router.push('/concierge/new')} testID="services-concierge" />
            ) : undefined
          }
        />
      )}
    </Screen>
  );
}
