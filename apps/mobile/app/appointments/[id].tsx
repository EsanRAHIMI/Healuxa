/**
 * Appointment detail. Uses appointment: getAppointment, listAppointmentTransitions,
 * transitionAppointment(cancel, reason customer_request) and links to the reschedule picker.
 * The server enforces the cancellation cut-off; a 409/422 is shown as-is, never hidden.
 */
import { randomUUID } from 'expo-crypto';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { Alert } from 'react-native';

import { ApiError } from '@/api/errors';
import { useAuth } from '@/auth/AuthProvider';
import { formatMoney } from '@/format/money';
import { formatDateTime } from '@/format/time';
import { errorKey, useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { useApi } from '@/services';
import { AppText, Button, Card, ErrorState, Loading, Row, Screen, Section } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';
import { StatusBadge } from '@/ui/StatusBadge';

export default function AppointmentDetail() {
  const { id, notice } = useLocalSearchParams<{ id: string; notice?: 'submitted' | 'rescheduled' }>();
  const { t, language } = useI18n();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const cancelKey = useRef(randomUUID());
  const signedIn = auth.status === 'signedIn';
  const appt = useRemote(() => (signedIn ? auth.withAuth((tk) => api.appointments.get(tk, id)) : Promise.resolve(null)), [api, id, signedIn, auth.withAuth]);
  const history = useRemote(
    () => (signedIn ? auth.withAuth((tk) => api.appointments.transitions(tk, id)) : Promise.resolve(null)),
    [api, id, signedIn, auth.withAuth, appt.data?.status]
  );

  if (!signedIn) return <SignedOutPrompt />;
  if (appt.loading) return <Screen><Loading /></Screen>;
  if (appt.error || !appt.data) return <Screen>{appt.error ? <ErrorState error={appt.error} onRetry={appt.reload} /> : null}</Screen>;

  const a = appt.data;
  const cancellable = a.status === 'held' || a.status === 'requested' || a.status === 'confirmed';
  const reschedulable = a.status === 'requested' || a.status === 'confirmed';

  const cancel = () =>
    Alert.alert(t('appointments.cancel'), t('appointments.cancelConfirm'), [
      { text: t('common.close'), style: 'cancel' },
      {
        text: t('appointments.cancel'),
        style: 'destructive',
        onPress: async () => {
          setBusy(true);
          try {
            await auth.withAuth((tk) => api.appointments.transition(tk, a.id, 'cancel', cancelKey.current, 'customer_request'));
            appt.reload();
          } catch (e) {
            Alert.alert(t('appointments.cancel'), t(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }))));
          } finally {
            setBusy(false);
          }
        },
      },
    ]);

  return (
    <Screen testID="appointment-screen" onRefresh={appt.reload} refreshing={appt.refreshing}>
      <Stack.Screen options={{ title: a.service_name ?? '' }} />
      {notice ? (
        <Card accessibilityRole="alert" testID="appointment-notice">
          <AppText>{t(notice === 'submitted' ? 'book.submitted' : 'book.rescheduled')}</AppText>
        </Card>
      ) : null}
      <AppText variant="title">{a.service_name}</AppText>
      <StatusBadge kind="appointments" status={a.status} />
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <AppText muted>{t('appointments.when')}</AppText>
          <AppText variant="label">{formatDateTime(a.scheduled_at, language, a.timezone)}</AppText>
        </Row>
        <AppText variant="caption" muted>{a.timezone}</AppText>
        <Row style={{ justifyContent: 'space-between' }}>
          <AppText muted>{t('appointments.duration')}</AppText>
          <AppText>{t('common.minutes', { n: a.duration_minutes })}</AppText>
        </Row>
        {a.price ? (
          <Row style={{ justifyContent: 'space-between' }}>
            <AppText muted>{t('appointments.price')}</AppText>
            <AppText>{formatMoney(a.price, language)}</AppText>
          </Row>
        ) : null}
      </Card>
      <Button kind="link" label={t('services.byProvider')} onPress={() => router.push({ pathname: '/providers/[id]', params: { id: a.provider_id } })} />
      {reschedulable ? (
        <Button
          kind="secondary"
          label={t('appointments.reschedule')}
          icon="calendar-outline"
          onPress={() => router.push({ pathname: '/book/[serviceId]', params: { serviceId: a.service_id, reschedule: a.id } })}
          testID="appointment-reschedule"
        />
      ) : null}
      {cancellable ? <Button kind="danger" label={t('appointments.cancel')} onPress={cancel} busy={busy} testID="appointment-cancel" /> : null}
      {a.rescheduled_to_id ? (
        <Button kind="link" label={t('appointments.status.rescheduled')} onPress={() => router.replace({ pathname: '/appointments/[id]', params: { id: a.rescheduled_to_id! } })} />
      ) : null}
      {history.data?.data.length ? (
        <Section title={t('appointments.history')}>
          <Card>
            {history.data.data.map((h) => (
              <Row key={h.id} style={{ justifyContent: 'space-between' }}>
                <AppText variant="small">{t(`appointments.status.${h.to_status}` as MessageKey)}</AppText>
                <AppText variant="caption" muted>{formatDateTime(h.occurred_at, language, a.timezone)}</AppText>
              </Row>
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
