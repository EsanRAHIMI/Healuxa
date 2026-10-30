import { Stack, useLocalSearchParams } from 'expo-router';
import { Linking } from 'react-native';

import type { Branch } from '@/api/types';
import { usePublic } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { facilityTypeLabel, localized, weekdayName } from '@/i18n/labels';
import { useApi } from '@/services';
import { AppText, Badge, Button, Card, EmptyState, ErrorState, Loading, OfflineBanner, Row, Screen, Section } from '@/ui/primitives';
import { OfferingCard } from '@/ui/OfferingCard';

function BranchCard({ branch }: { branch: Branch }) {
  const { t, language } = useI18n();
  const api = useApi();
  const hours = usePublic(() => api.directory.getOperatingHours(branch.id), [api, branch.id]);
  const byDay = new Map<number, string[]>();
  for (const w of hours.data?.windows ?? []) byDay.set(w.weekday, [...(byDay.get(w.weekday) ?? []), `${w.start}–${w.end}`]);
  return (
    <Card testID={`branch-${branch.id}`}>
      <AppText variant="label">{branch.name}</AppText>
      <AppText variant="small" muted>
        {[branch.address_line, branch.city, branch.emirate].filter(Boolean).join(', ')}
      </AppText>
      <AppText variant="label" style={{ marginTop: 8 }}>{t('facility.hours')}</AppText>
      {hours.loading ? (
        <Loading />
      ) : hours.error ? (
        <ErrorState error={hours.error} onRetry={hours.reload} />
      ) : (
        [0, 1, 2, 3, 4, 5, 6].map((d) => (
          <Row key={d} style={{ justifyContent: 'space-between' }} accessible accessibilityLabel={`${weekdayName(d, language)}: ${byDay.get(d)?.join(', ') ?? t('facility.closed')}`}>
            <AppText variant="small">{weekdayName(d, language)}</AppText>
            <AppText variant="small" muted>{byDay.get(d)?.join(', ') ?? t('facility.closed')}</AppText>
          </Row>
        ))
      )}
      {hours.data?.timezone ? <AppText variant="caption" muted>{hours.data.timezone}</AppText> : null}
      {branch.phone ? (
        <Button kind="link" icon="call-outline" label={t('facility.call', { name: branch.name })} onPress={() => Linking.openURL(`tel:${branch.phone}`)} />
      ) : null}
    </Card>
  );
}

/** Facility page. Uses provider: getFacility, listBranches, getOperatingHours, listServices(facility_id). */
export default function FacilityPage() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, language } = useI18n();
  const api = useApi();
  const facility = usePublic(() => api.directory.getFacility(id), [api, id]);
  const branches = usePublic(() => api.directory.listBranches(id), [api, id]);
  const services = usePublic(() => api.directory.listServices({ facility_id: id, limit: 100 }), [api, id]);

  if (facility.loading) return <Screen><Loading /></Screen>;
  if (facility.error || !facility.data) {
    return <Screen>{facility.error ? <ErrorState error={facility.error} onRetry={facility.reload} /> : null}</Screen>;
  }
  const f = facility.data;
  const about = localized(f.description, language);
  return (
    <Screen testID="facility-screen" onRefresh={facility.reload} refreshing={facility.refreshing}>
      <Stack.Screen options={{ title: f.name }} />
      {facility.fromCache ? <OfflineBanner storedAt={facility.storedAt} /> : null}
      <AppText variant="title" testID="facility-name">{f.name}</AppText>
      <Row>
        <AppText muted>{facilityTypeLabel(f.type, language)}</AppText>
        {f.verification_status === 'verified' ? <Badge label={t('common.verified')} icon="shield-checkmark" /> : null}
      </Row>
      {about ? (
        <Section title={t('facility.about')}>
          <AppText>{about}</AppText>
        </Section>
      ) : null}
      {f.website ? (
        <Button kind="link" icon="globe-outline" label={t('facility.website')} onPress={() => Linking.openURL(f.website!)} />
      ) : null}
      <Section title={t('facility.branches')}>
        {branches.loading ? (
          <Loading />
        ) : branches.error ? (
          <ErrorState error={branches.error} onRetry={branches.reload} />
        ) : (
          branches.data?.data.map((b) => <BranchCard key={b.id} branch={b} />)
        )}
      </Section>
      <Section title={t('facility.services')}>
        {services.loading ? (
          <Loading />
        ) : services.error && !services.data ? (
          <ErrorState error={services.error} onRetry={services.reload} />
        ) : services.data?.data.length ? (
          services.data.data.map((s) => <OfferingCard key={s.id} offering={s} showProviderLink />)
        ) : (
          <EmptyState message={t('services.empty')} />
        )}
      </Section>
    </Screen>
  );
}
