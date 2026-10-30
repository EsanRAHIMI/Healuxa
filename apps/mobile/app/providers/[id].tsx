import { Stack, useLocalSearchParams, useRouter } from 'expo-router';

import { usePublic } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { credentialKindLabel, formatDate, languageName, localized, providerTypeLabel } from '@/i18n/labels';
import { useApi } from '@/services';
import { AppText, Badge, Card, Chip, EmptyState, ErrorState, Loading, OfflineBanner, PressableCard, Row, Screen, Section } from '@/ui/primitives';
import { OfferingCard } from '@/ui/OfferingCard';

/**
 * Provider profile. Uses provider: getProvider, listServices(provider_id), getFacility (for the
 * facilities the offerings are delivered at).
 */
export default function ProviderProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, language } = useI18n();
  const api = useApi();
  const router = useRouter();
  const provider = usePublic(() => api.directory.getProvider(id), [api, id]);
  const services = usePublic(() => api.directory.listServices({ provider_id: id, limit: 100 }), [api, id]);
  const facilityIds = Array.from(new Set((services.data?.data ?? []).map((s) => s.facility_id).filter((f): f is string => Boolean(f))));
  const facilities = usePublic(
    async () => {
      const results = await Promise.all(facilityIds.map((f) => api.directory.getFacility(f)));
      return { data: results.map((r) => r.data), fromCache: results.some((r) => r.fromCache) };
    },
    [api, facilityIds.join(',')]
  );

  if (provider.loading) return <Screen><Loading /></Screen>;
  if (provider.error || !provider.data) {
    return (
      <Screen>
        {provider.error ? <ErrorState error={provider.error} onRetry={provider.reload} /> : null}
      </Screen>
    );
  }
  const p = provider.data;
  const bio = localized(p.bio, language);
  return (
    <Screen testID="provider-screen" onRefresh={() => { provider.reload(); services.reload(); }} refreshing={provider.refreshing}>
      <Stack.Screen options={{ title: p.display_name }} />
      {provider.fromCache ? <OfflineBanner storedAt={provider.storedAt} /> : null}
      <AppText variant="title" testID="provider-name">{p.display_name}</AppText>
      <Row>
        <AppText muted>{p.title ?? providerTypeLabel(p.type, language)}</AppText>
        {p.verification_status === 'verified' ? <Badge label={t('common.verified')} icon="shield-checkmark" /> : null}
      </Row>

      <Section title={t('provider.credentials')} testID="provider-credentials">
        <Card>
          {p.verified_credentials?.length ? (
            p.verified_credentials.map((c, i) => (
              <Row key={i} accessible accessibilityLabel={`${credentialKindLabel(c.kind, language)}, ${c.issuing_authority ?? ''}`}>
                <Badge label={credentialKindLabel(c.kind, language)} icon="ribbon-outline" />
                <AppText variant="small">{c.issuing_authority}</AppText>
                {c.valid_until ? (
                  <AppText variant="caption" muted>
                    {t('provider.credentialValidUntil', { date: formatDate(c.valid_until, language) })}
                  </AppText>
                ) : null}
              </Row>
            ))
          ) : (
            <AppText variant="small" muted>{t('provider.noCredentials')}</AppText>
          )}
        </Card>
      </Section>

      {bio ? (
        <Section title={t('provider.about')}>
          <AppText>{bio}</AppText>
        </Section>
      ) : null}

      <Section title={t('provider.specialties')}>
        <Row>{p.specialties.map((s) => <Chip key={s} label={s} />)}</Row>
      </Section>
      <Section title={t('provider.languages')}>
        <Row>{p.languages.map((l) => <Chip key={l} label={languageName(l, language)} />)}</Row>
      </Section>

      {facilities.data?.length ? (
        <Section title={t('provider.practisesAt')}>
          {facilities.data.map((f) => (
            <PressableCard
              key={f.id}
              testID={`provider-facility-${f.id}`}
              accessibilityLabel={f.name}
              onPress={() => router.push({ pathname: '/facilities/[id]', params: { id: f.id } })}
            >
              <AppText variant="label">{f.name}</AppText>
            </PressableCard>
          ))}
        </Section>
      ) : null}

      <Section title={t('provider.offerings')} testID="provider-offerings">
        <AppText variant="small" muted>{t('fees.disclaimer')}</AppText>
        {services.loading ? (
          <Loading />
        ) : services.error && !services.data ? (
          <ErrorState error={services.error} onRetry={services.reload} />
        ) : services.data?.data.length ? (
          services.data.data.map((s) => <OfferingCard key={s.id} offering={s} />)
        ) : (
          <EmptyState message={t('provider.noOfferings')} />
        )}
      </Section>
    </Screen>
  );
}
