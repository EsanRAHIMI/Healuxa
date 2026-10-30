import { useMemo, useState } from 'react';
import { ScrollView } from 'react-native';

import { usePublic } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Chip, EmptyState, ErrorState, Loading, OfflineBanner, Screen } from '@/ui/primitives';
import { OfferingCard } from '@/ui/OfferingCard';

/** Services catalog. Uses provider: listServices (all, then filtered by category). */
export default function Services() {
  const { t } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const [category, setCategory] = useState<string | undefined>();
  const all = usePublic(() => api.directory.listServices({ limit: 100 }), [api]);
  const filtered = usePublic(
    () => (category ? api.directory.listServices({ category, limit: 100 }) : Promise.resolve({ data: { data: [], page: { limit: 0, has_more: false } }, fromCache: false })),
    [api, category]
  );
  const categories = useMemo(
    () => Array.from(new Set((all.data?.data ?? []).map((s) => s.category))).sort(),
    [all.data]
  );
  const shown = category ? filtered : all;

  return (
    <Screen testID="services-screen" onRefresh={shown.reload} refreshing={shown.refreshing}>
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
        shown.data.data.map((s) => <OfferingCard key={s.id} offering={s} showProviderLink />)
      ) : (
        <EmptyState message={t('services.empty')} />
      )}
    </Screen>
  );
}
