import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';

import type { Appointment } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { formatDateTime } from '@/format/time';
import { useRemote } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { useApi } from '@/services';
import { AppText, Button, EmptyState, ErrorState, Loading, PressableCard, Screen, Section } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';
import { StatusBadge } from '@/ui/StatusBadge';

const ACTIVE = new Set(['held', 'requested', 'confirmed', 'checked_in']);

/** My bookings. Uses appointment: listAppointments (own appointments, newest schedule first). */
export default function Bookings() {
  const { t, language } = useI18n();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const signedIn = auth.status === 'signedIn';
  const list = useRemote(
    () => (signedIn ? auth.withAuth((tk) => api.appointments.list(tk, { sort: '-scheduled_at' })) : Promise.resolve(null)),
    [api, signedIn, auth.withAuth]
  );
  // Refresh when the tab regains focus (after booking, cancelling or rescheduling).
  const { reload } = list;
  useFocusEffect(useCallback(() => reload(), [reload]));
  const [now] = useState(() => Date.now());

  if (!signedIn) return <SignedOutPrompt />;

  const all = list.data?.data ?? [];
  const upcoming = all.filter((a) => ACTIVE.has(a.status) && new Date(a.ends_at).getTime() >= now).reverse();
  const past = all.filter((a) => !upcoming.includes(a));

  const card = (a: Appointment) => (
    <PressableCard
      key={a.id}
      testID={`appointment-${a.id}`}
      accessibilityLabel={`${a.service_name ?? ''} ${formatDateTime(a.scheduled_at, language, a.timezone)}`}
      onPress={() => router.push({ pathname: '/appointments/[id]', params: { id: a.id } })}
    >
      <AppText variant="label">{a.service_name ?? t('tabs.bookings')}</AppText>
      <AppText variant="small" muted>{formatDateTime(a.scheduled_at, language, a.timezone)}</AppText>
      <StatusBadge kind="appointments" status={a.status} />
    </PressableCard>
  );

  return (
    <Screen testID="bookings-screen" onRefresh={list.reload} refreshing={list.refreshing}>
      {list.loading ? (
        <Loading />
      ) : list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : !all.length ? (
        <EmptyState
          message={t('appointments.empty')}
          action={<Button kind="secondary" label={t('appointments.browse')} onPress={() => router.navigate('/directory')} />}
        />
      ) : (
        <>
          {upcoming.length ? <Section title={t('appointments.upcoming')}>{upcoming.map(card)}</Section> : null}
          {past.length ? <Section title={t('appointments.past')}>{past.map(card)}</Section> : null}
        </>
      )}
    </Screen>
  );
}
