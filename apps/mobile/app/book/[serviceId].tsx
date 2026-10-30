/**
 * Booking flow (appointment-service), and the same picker for rescheduling.
 *
 *   listAvailableSlots → createAppointment (hold, Idempotency-Key) → transitionAppointment(submit)
 *   reschedule mode (?reschedule=<id>): listAvailableSlots → rescheduleAppointment
 *
 * Slots come only from the server (derived from provider availability); a 503 means availability
 * cannot be checked and no times are shown. A hold that the user abandons is released with the
 * `cancel` transition; otherwise it expires server-side at hold_expires_at.
 */
import { randomUUID } from 'expo-crypto';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, View } from 'react-native';

import { ApiError } from '@/api/errors';
import type { Appointment, Slot } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { formatDuration } from '@/format/money';
import { formatDayHeading, formatTime, isoDateInZone, localDate } from '@/format/time';
import { errorKey, usePublic, useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { FeeBreakdownView } from '@/ui/FeeBreakdownView';
import { AppText, Button, Card, Chip, EmptyState, ErrorState, Loading, Row, Screen, Section } from '@/ui/primitives';

const WINDOW_DAYS = 14;
const DEFAULT_TZ = 'Asia/Dubai';

export default function Book() {
  const { serviceId, reschedule } = useLocalSearchParams<{ serviceId: string; reschedule?: string }>();
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();

  const [offset, setOffset] = useState(0);
  const [day, setDay] = useState<string | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [hold, setHold] = useState<Appointment | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<MessageKey | null>(null);
  // One idempotency key per user intent; a retry of the same action replays instead of duplicating.
  const keys = useRef<Record<string, string>>({});
  const keyFor = (action: string) => (keys.current[action] ??= randomUUID());

  const service = usePublic(() => api.directory.getService(serviceId), [api, serviceId]);
  const [tz, setTz] = useState(DEFAULT_TZ);
  const from = isoDateInZone(offset, tz);
  const to = isoDateInZone(offset + WINDOW_DAYS - 1, tz);
  const slots = useRemote(() => api.appointments.listSlots(serviceId, from, to), [api, serviceId, from, to]);

  // The branch time zone is only known from the first slot response; re-anchor the window to it.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (slots.data?.timezone && slots.data.timezone !== tz) setTz(slots.data.timezone);
  }, [slots.data?.timezone, tz]);

  const byDay = useMemo(() => {
    const map = new Map<string, Slot[]>();
    for (const s of slots.data?.slots ?? []) {
      const d = localDate(s.local_start);
      map.set(d, [...(map.get(d) ?? []), s]);
    }
    return map;
  }, [slots.data]);
  const days = Array.from(byDay.keys());
  const activeDay = day && byDay.has(day) ? day : days[0];

  // Release an abandoned hold when the screen is left without submitting.
  const holdRef = useRef<Appointment | null>(null);
  useEffect(() => {
    holdRef.current = hold;
  }, [hold]);
  useEffect(
    () => () => {
      const h = holdRef.current;
      if (h && h.status === 'held') {
        auth.withAuth((tk) => api.appointments.transition(tk, h.id, 'cancel', randomUUID(), 'customer_request')).catch(() => undefined);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const fail = (e: unknown) => {
    const err = e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' });
    if (err.status === 409) {
      setNotice('book.slotTaken');
      setSlot(null);
      slots.reload();
    } else if (err.status === 503) setNotice('book.unavailable');
    else setNotice(errorKey(err));
  };

  const choose = async (s: Slot) => {
    setNotice(null);
    setSlot(s);
    if (auth.status !== 'signedIn') return;
    if (reschedule) return; // confirmed explicitly below
    setBusy(true);
    try {
      if (hold) {
        // Moving to another time: release the previous hold first.
        await auth.withAuth((tk) => api.appointments.transition(tk, hold.id, 'cancel', keyFor(`release-${hold.id}`), 'customer_request'));
        setHold(null);
      }
      const created = await auth.withAuth((tk) =>
        api.appointments.hold(tk, { service_id: serviceId, scheduled_at: s.scheduled_at }, keyFor(`hold-${s.scheduled_at}`))
      );
      setHold(created);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!hold) return;
    setBusy(true);
    try {
      const requested = await auth.withAuth((tk) => api.appointments.transition(tk, hold.id, 'submit', keyFor(`submit-${hold.id}`)));
      setHold(null);
      router.replace({ pathname: '/appointments/[id]', params: { id: requested.id, notice: 'submitted' } });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const confirmReschedule = async () => {
    if (!slot || !reschedule) return;
    setBusy(true);
    try {
      const moved = await auth.withAuth((tk) =>
        api.appointments.reschedule(tk, reschedule, slot.scheduled_at, keyFor(`reschedule-${slot.scheduled_at}`))
      );
      router.replace({ pathname: '/appointments/[id]', params: { id: moved.id, notice: 'rescheduled' } });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const offering = service.data;
  return (
    <Screen testID="book-screen">
      <Stack.Screen options={{ title: reschedule ? t('book.reschedule') : t('book.title') }} />
      {offering ? (
        <Card>
          <AppText variant="label">{offering.name}</AppText>
          <AppText variant="caption" muted>{formatDuration(offering.duration_minutes, language)}</AppText>
          <FeeBreakdownView offering={offering} />
        </Card>
      ) : null}

      <AppText variant="small" muted>{t('book.timezone', { tz })}</AppText>
      <Row style={{ justifyContent: 'space-between' }}>
        <Button kind="link" label={t('book.earlier')} disabled={offset === 0} onPress={() => setOffset((o) => Math.max(0, o - WINDOW_DAYS))} />
        <Button kind="link" label={t('book.later')} disabled={offset >= 28} onPress={() => setOffset((o) => o + WINDOW_DAYS)} testID="book-later" />
      </Row>

      {slots.loading ? (
        <Loading />
      ) : slots.error ? (
        slots.error.status === 503 ? (
          <EmptyState message={t('book.unavailable')} action={<Button kind="secondary" label={t('common.retry')} onPress={slots.reload} />} />
        ) : (
          <ErrorState error={slots.error} onRetry={slots.reload} />
        )
      ) : !days.length ? (
        <EmptyState message={t('book.noSlots')} />
      ) : (
        <>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: theme.space(2) }}>
            {days.map((d) => (
              <Chip
                key={d}
                label={formatDayHeading(byDay.get(d)![0]!.scheduled_at, language, tz)}
                selected={d === activeDay}
                onPress={() => setDay(d)}
                testID={`book-day-${d}`}
              />
            ))}
          </ScrollView>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space(2) }}>
            {(activeDay ? byDay.get(activeDay) ?? [] : []).map((s) => (
              <Chip
                key={s.scheduled_at}
                label={formatTime(s.scheduled_at, language, tz)}
                selected={slot?.scheduled_at === s.scheduled_at}
                onPress={() => choose(s)}
                testID={`book-slot-${s.scheduled_at}`}
              />
            ))}
          </View>
        </>
      )}

      {notice ? (
        <Card accessibilityRole="alert" style={{ borderColor: theme.color.danger }} testID="book-notice">
          <AppText>{t(notice)}</AppText>
        </Card>
      ) : null}

      {slot && auth.status !== 'signedIn' ? (
        <Card>
          <AppText>{t('common.signInRequired')}</AppText>
          <Button label={t('welcome.signIn')} onPress={() => router.push('/sign-in')} />
        </Card>
      ) : null}

      {slot && reschedule && auth.status === 'signedIn' ? (
        <Section title={t('book.review')}>
          <Card>
            <AppText variant="label">{formatDayHeading(slot.scheduled_at, language, tz)} · {formatTime(slot.scheduled_at, language, tz)}</AppText>
            <Button label={t('book.reschedule')} onPress={confirmReschedule} busy={busy} testID="book-confirm-reschedule" />
          </Card>
        </Section>
      ) : null}

      {busy && !hold && !reschedule ? <AppText muted>{t('book.holding')}</AppText> : null}
      {hold ? (
        <Section title={t('book.review')}>
          <Card testID="book-hold">
            <AppText variant="label">{formatDayHeading(hold.scheduled_at, language, hold.timezone)} · {formatTime(hold.scheduled_at, language, hold.timezone)}</AppText>
            {hold.hold_expires_at ? (
              <AppText variant="small" muted>{t('book.heldUntil', { time: formatTime(hold.hold_expires_at, language, hold.timezone) })}</AppText>
            ) : null}
            <Button label={t('book.submit')} onPress={submit} busy={busy} testID="book-submit" />
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
