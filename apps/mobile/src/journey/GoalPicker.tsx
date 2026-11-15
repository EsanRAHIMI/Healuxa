import { useState } from 'react';
import { View } from 'react-native';

import { GOAL_CODES, type GoalCode } from '../api/types';
import { type MessageKey, useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText, Button } from '../ui/primitives';
import { Choice } from './Choice';
import { MAX_GOALS, toggleGoal } from './plan';

/**
 * Goal picker for a new journey: 1–3 goals, kept in the order they were chosen (their priority).
 * Once three are chosen the remaining options are disabled and a note explains why.
 */
export function GoalPicker({
  onSubmit,
  busy,
  error,
}: {
  onSubmit: (goals: GoalCode[]) => void;
  busy?: boolean;
  error?: MessageKey | null;
}) {
  const { t } = useI18n();
  const theme = useTheme();
  const [selected, setSelected] = useState<GoalCode[]>([]);
  const full = selected.length >= MAX_GOALS;

  return (
    <View style={{ gap: theme.space(4) }} testID="goal-picker">
      <View style={{ gap: theme.space(1) }}>
        <AppText variant="heading">{t('journey.goals.title')}</AppText>
        <AppText muted>{t('journey.goals.hint', { max: MAX_GOALS })}</AppText>
      </View>
      <View style={{ gap: theme.space(2) }}>
        {GOAL_CODES.map((goal) => {
          const index = selected.indexOf(goal);
          return (
            <Choice
              key={goal}
              role="checkbox"
              label={t(`journey.goal.${goal}`)}
              selected={index >= 0}
              badge={index >= 0 ? String(index + 1) : undefined}
              disabled={busy || (full && index < 0)}
              onPress={() => setSelected((cur) => toggleGoal(cur, goal))}
              testID={`goal-${goal}`}
            />
          );
        })}
      </View>
      <AppText variant="small" muted accessibilityLiveRegion="polite" testID="goal-count">
        {full ? t('journey.goals.limit', { max: MAX_GOALS }) : t('journey.goals.count', { n: selected.length, max: MAX_GOALS })}
      </AppText>
      <AppText variant="small" muted>{t('journey.goals.disclaimer')}</AppText>
      {error ? (
        <AppText style={{ color: theme.color.danger }} accessibilityRole="alert" testID="goal-error">
          {t(error)}
        </AppText>
      ) : null}
      <Button label={t('journey.goals.submit')} onPress={() => onSubmit(selected)} disabled={!selected.length} busy={busy} testID="goal-submit" />
    </View>
  );
}
