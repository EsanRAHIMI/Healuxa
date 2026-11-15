/**
 * Personalised journey: the customer's goal-driven coordination plan.
 *
 *   no journey  → goal picker → createJourney (Idempotency-Key) → /journey/intake
 *   journey     → getRoadmap: four phases with their steps, progress and the next action
 *   actions     → intake form · services filtered by the step's category (the step id travels to
 *                 createAppointment as milestone_id) · concierge · completeMilestone · closeJourney
 *
 * Coordination only: nothing here recommends a treatment or a test. After the intake form is saved
 * the plan updates asynchronously, so the screen re-fetches a few times and then stays usable.
 */
import { randomUUID } from 'expo-crypto';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, View } from 'react-native';

import { ApiError } from '@/api/errors';
import type { GoalCode, Milestone } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey, useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { GoalPicker } from '@/journey/GoalPicker';
import { loadJourneyPlan } from '@/journey/load';
import { goalLabel, intakeCompleted, progress, stepLabel } from '@/journey/plan';
import { Timeline } from '@/journey/Timeline';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Chip, EmptyState, ErrorState, Loading, Row, Screen, Section } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

/** After the intake form: re-fetch this many times, this far apart, until the intake step is done. */
export const INTAKE_POLL_ATTEMPTS = 5;
export const INTAKE_POLL_INTERVAL_MS = 2000;

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }));

export default function JourneyScreen() {
  const { notice } = useLocalSearchParams<{ notice?: 'intake_saved' }>();
  const { t } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const signedIn = auth.status === 'signedIn';
  const userId = auth.userId;

  const plan = useRemote(
    () => (signedIn && userId ? auth.withAuth((tk) => loadJourneyPlan(api, tk, userId)) : Promise.resolve(null)),
    [api, signedIn, userId, auth.withAuth]
  );
  // Refresh when the screen regains focus (after the intake form, a booking or a concierge request).
  const { reload } = plan;
  useFocusEffect(useCallback(() => reload(), [reload]));

  const [creating, setCreating] = useState(false);
  const [flash, setFlash] = useState<MessageKey | null>(null);
  const [busyStepId, setBusyStepId] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [noticeClosed, setNoticeClosed] = useState(false);
  const [pollsUsed, setPollsUsed] = useState(0);
  // One idempotency key per user intent; a retry of the same action replays instead of duplicating.
  const keys = useRef<Record<string, string>>({});
  const keyFor = (action: string) => (keys.current[action] ??= randomUUID());

  const journey = plan.data?.journey ?? null;
  const roadmap = plan.data?.roadmap ?? null;
  const intakeDone = intakeCompleted(roadmap);
  const intakeSaved = notice === 'intake_saved' && Boolean(journey);
  const polling = intakeSaved && !intakeDone && pollsUsed < INTAKE_POLL_ATTEMPTS;

  useEffect(() => {
    if (!polling || plan.loading || plan.refreshing) return;
    const timer = setTimeout(() => {
      setPollsUsed((n) => n + 1);
      reload();
    }, INTAKE_POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [polling, plan.loading, plan.refreshing, reload]);

  if (!signedIn || !userId) return <SignedOutPrompt intro={t('journey.signedOutIntro')} />;

  const create = async (goals: GoalCode[]) => {
    if (!goals.length) return;
    const intent = `create-${goals.join(',')}`;
    setCreating(true);
    setFlash(null);
    try {
      await auth.withAuth((tk) => api.journeys.create(tk, { user_id: userId, primary_goals: goals }, keyFor(intent)));
      delete keys.current[intent];
      router.push('/journey/intake');
      reload();
    } catch (e) {
      const err = asApiError(e);
      if (err.status === 409) {
        // A journey already exists (for example it was started on the web): show it instead.
        setFlash('journey.alreadyActive');
        reload();
      } else setFlash(errorKey(err));
    } finally {
      setCreating(false);
    }
  };

  const markDone = (step: Milestone) => {
    if (!journey) return;
    const label = stepLabel(step, t);
    Alert.alert(t('journey.action.markDone'), t('journey.markDone.confirm', { step: label }), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('journey.action.markDone'),
        onPress: async () => {
          setBusyStepId(step.id);
          try {
            await auth.withAuth((tk) => api.journeys.completeMilestone(tk, journey.id, step.id, keyFor(`complete-${step.id}`)));
            reload();
          } catch (e) {
            const err = asApiError(e);
            // 409: the step was completed elsewhere in the meantime; the refreshed plan shows it.
            if (err.status === 409) reload();
            else Alert.alert(t('journey.action.markDone'), t(errorKey(err)));
          } finally {
            setBusyStepId(null);
          }
        },
      },
    ]);
  };

  const end = () => {
    if (!journey) return;
    Alert.alert(t('journey.end'), t('journey.end.confirm'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('journey.end'),
        style: 'destructive',
        onPress: async () => {
          setEnding(true);
          try {
            await auth.withAuth((tk) => api.journeys.close(tk, journey.id));
            setFlash(null);
            reload();
          } catch (e) {
            Alert.alert(t('journey.end'), t(errorKey(asApiError(e))));
          } finally {
            setEnding(false);
          }
        },
      },
    ]);
  };

  const { done, total } = progress(roadmap);
  const intakeNotice: MessageKey = intakeDone ? 'journey.intakeUpdated' : polling ? 'journey.intakeSaved' : 'journey.intakeDelayed';

  return (
    // The pull-to-refresh spinner is reserved for the customer's own refresh, not background polling.
    <Screen testID="journey-screen" onRefresh={plan.reload} refreshing={plan.refreshing && !polling}>
      {plan.loading ? (
        <Loading />
      ) : plan.error && !plan.data ? (
        <ErrorState error={plan.error} onRetry={plan.reload} />
      ) : !journey ? (
        <>
          <AppText muted>{t('journey.intro')}</AppText>
          <GoalPicker onSubmit={create} busy={creating} error={flash} />
        </>
      ) : (
        <>
          {flash ? (
            <Card accessibilityRole="alert" testID="journey-flash">
              <AppText>{t(flash)}</AppText>
            </Card>
          ) : null}
          {intakeSaved && !noticeClosed ? (
            <Card accessibilityRole="alert" accessibilityLiveRegion="polite" testID="journey-intake-notice">
              <AppText>{t(intakeNotice)}</AppText>
              {!polling ? <Button kind="link" label={t('common.close')} onPress={() => setNoticeClosed(true)} testID="journey-intake-notice-close" /> : null}
            </Card>
          ) : null}
          {plan.error ? <ErrorState error={plan.error} onRetry={plan.reload} /> : null}

          <Section title={t('journey.goalsHeading')}>
            <Row>
              {journey.primary_goals.map((g) => (
                <Chip key={g} label={goalLabel(g, t) ?? g} />
              ))}
            </Row>
          </Section>

          {total ? (
            <View style={{ gap: theme.space(2) }}>
              <AppText variant="label" testID="journey-progress">{t('journey.progress', { done, total })}</AppText>
              <View
                accessibilityRole="progressbar"
                accessibilityLabel={t('journey.progress', { done, total })}
                accessibilityValue={{ min: 0, max: total, now: done }}
                style={{ height: 8, borderRadius: theme.radius.pill, backgroundColor: theme.color.surfaceAlt, overflow: 'hidden', flexDirection: 'row' }}
              >
                <View style={{ flex: done, backgroundColor: theme.color.accent }} />
                <View style={{ flex: total - done }} />
              </View>
            </View>
          ) : null}

          <Section title={t('journey.plan')}>
            {roadmap && total ? (
              <Timeline
                roadmap={roadmap}
                appointments={plan.data?.appointments ?? {}}
                busyStepId={busyStepId}
                handlers={{
                  onIntake: () => router.push('/journey/intake'),
                  onBook: (step) =>
                    router.push({
                      pathname: '/services',
                      params: step.service_category ? { category: step.service_category, milestoneId: step.id } : { milestoneId: step.id },
                    }),
                  onConcierge: () => router.push('/concierge/new'),
                  onMarkDone: markDone,
                  onAppointment: (id) => router.push({ pathname: '/appointments/[id]', params: { id } }),
                }}
              />
            ) : (
              <EmptyState
                message={t('journey.empty')}
                action={<Button kind="secondary" label={t('journey.action.concierge')} onPress={() => router.push('/concierge/new')} />}
              />
            )}
          </Section>

          <Row style={{ justifyContent: 'center' }}>
            <Button kind="link" label={t('journey.end')} onPress={end} busy={ending} testID="journey-end" />
          </Row>
        </>
      )}
    </Screen>
  );
}
