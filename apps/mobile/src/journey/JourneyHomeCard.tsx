import { useRouter } from 'expo-router';

import type { RemoteState } from '../hooks/useRemote';
import { useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText, Button, Card, Loading } from '../ui/primitives';
import type { JourneySummary } from './load';
import { currentPhase, phaseLabel, progress, stepLabel } from './plan';

/**
 * Home entry point for the journey. Signed out or without a journey it invites the customer to
 * start one; otherwise it shows the current phase, the next step and overall progress.
 */
export function JourneyHomeCard({ summary }: { summary: RemoteState<JourneySummary | null> }) {
  const { t } = useI18n();
  const theme = useTheme();
  const router = useRouter();
  const open = () => router.push('/journey');
  const data = summary.data;
  const frame = { borderColor: theme.color.accent, borderWidth: 1 };

  if (summary.loading) {
    return (
      <Card style={frame} testID="home-journey">
        <AppText variant="heading">{t('journey.home.title')}</AppText>
        <Loading />
      </Card>
    );
  }

  if (summary.error && !data) {
    return (
      <Card style={frame} testID="home-journey">
        <AppText variant="heading">{t('journey.home.title')}</AppText>
        <AppText muted accessibilityRole="alert">{t('journey.home.unavailable')}</AppText>
        <Button kind="secondary" label={t('common.retry')} onPress={summary.reload} testID="home-journey-retry" />
      </Card>
    );
  }

  if (!data?.journey) {
    return (
      <Card style={frame} testID="home-journey">
        <AppText variant="heading">{t('journey.home.startTitle')}</AppText>
        <AppText muted>{t('journey.home.startBody')}</AppText>
        <Button label={t('journey.home.startTitle')} icon="compass-outline" onPress={open} testID="home-journey-start" />
      </Card>
    );
  }

  const phase = currentPhase(data.roadmap);
  const next = data.nextActions[0];
  const { done, total } = progress(data.roadmap);
  return (
    <Card style={frame} testID="home-journey">
      <AppText variant="heading">{t('journey.home.title')}</AppText>
      {phase ? <AppText testID="home-journey-phase">{t('journey.home.phase', { phase: phaseLabel(phase, t) })}</AppText> : null}
      <AppText variant="label" testID="home-journey-next">
        {next?.milestone_code
          ? t('journey.home.next', { step: stepLabel({ code: next.milestone_code, goal: next.goal }, t) })
          : t('journey.home.noNext')}
      </AppText>
      {total ? <AppText variant="small" muted>{t('journey.progress', { done, total })}</AppText> : null}
      <Button label={t('journey.home.open')} icon="compass-outline" onPress={open} testID="home-journey-open" />
    </Card>
  );
}
