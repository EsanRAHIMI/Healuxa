import { Ionicons } from '@expo/vector-icons';
import { View } from 'react-native';

import type { Appointment, Milestone, Roadmap, RoadmapPhase } from '../api/types';
import { formatDateTime } from '../format/time';
import { type MessageKey, useI18n } from '../i18n';
import { type Theme, useTheme } from '../theme';
import { AppText, Button, Card, Row } from '../ui/primitives';
import { phaseLabel, sortedPhases, sortedSteps, stepAction, stepLabel, stepStatusKey } from './plan';

export interface StepHandlers {
  onIntake: () => void;
  onBook: (step: Milestone) => void;
  onConcierge: () => void;
  onMarkDone: (step: Milestone) => void;
  onAppointment: (appointmentId: string) => void;
}

type IconName = keyof typeof Ionicons.glyphMap;

function stepIcon(step: Milestone, actionable: boolean, theme: Theme): { name: IconName; color: string } {
  switch (step.status) {
    case 'completed':
      return { name: 'checkmark-circle', color: theme.color.success };
    case 'scheduled':
      return { name: 'calendar', color: theme.color.accent };
    case 'in_progress':
      return { name: 'time-outline', color: theme.color.accent };
    case 'blocked':
      return { name: 'pause-circle-outline', color: theme.color.danger };
    default:
      return { name: 'ellipse-outline', color: actionable ? theme.color.accent : theme.color.textMuted };
  }
}

/** The four phases in order, each with its steps, their status and (for the current phase) actions. */
export function Timeline({
  roadmap,
  appointments,
  handlers,
  busyStepId,
}: {
  roadmap: Roadmap;
  appointments: Record<string, Appointment>;
  handlers: StepHandlers;
  busyStepId?: string | null;
}) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space(3) }} testID="journey-timeline">
      {sortedPhases(roadmap).map((phase) => (
        <PhaseCard key={phase.id} phase={phase} appointments={appointments} handlers={handlers} busyStepId={busyStepId} />
      ))}
    </View>
  );
}

function PhaseCard({
  phase,
  appointments,
  handlers,
  busyStepId,
}: {
  phase: RoadmapPhase;
  appointments: Record<string, Appointment>;
  handlers: StepHandlers;
  busyStepId?: string | null;
}) {
  const { t } = useI18n();
  const theme = useTheme();
  const current = phase.status === 'in_progress';
  const statusColor = phase.status === 'completed' ? theme.color.success : current ? theme.color.accent : theme.color.textMuted;
  const name = phaseLabel(phase, t);
  const status = t(`journey.phaseStatus.${phase.status}` as MessageKey);
  const steps = sortedSteps(phase);
  return (
    <Card
      testID={`phase-${phase.code ?? phase.id}`}
      style={[{ gap: theme.space(3) }, current ? { borderColor: theme.color.accent, borderWidth: 2 } : null, phase.status === 'pending' ? { opacity: 0.8 } : null]}
    >
      <Row style={{ justifyContent: 'space-between' }}>
        <AppText variant="heading" accessibilityLabel={`${name}, ${status}`} style={{ flexShrink: 1 }}>
          {name}
        </AppText>
        <View
          style={{ borderRadius: theme.radius.pill, borderWidth: 1, borderColor: statusColor, paddingHorizontal: theme.space(2), paddingVertical: 2 }}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          <AppText variant="caption" style={{ color: statusColor, fontWeight: '600' }}>
            {status}
          </AppText>
        </View>
      </Row>
      {steps.map((step, i) => (
        <View
          key={step.id}
          style={i > 0 ? { borderTopWidth: 1, borderTopColor: theme.color.border, paddingTop: theme.space(3) } : undefined}
        >
          <StepRow phase={phase} step={step} appointment={step.appointment_id ? appointments[step.appointment_id] : undefined} handlers={handlers} busy={busyStepId === step.id} />
        </View>
      ))}
    </Card>
  );
}

function StepRow({
  phase,
  step,
  appointment,
  handlers,
  busy,
}: {
  phase: RoadmapPhase;
  step: Milestone;
  appointment?: Appointment;
  handlers: StepHandlers;
  busy: boolean;
}) {
  const { t, language } = useI18n();
  const theme = useTheme();
  const action = stepAction(phase, step);
  const label = stepLabel(step, t);
  const status = t(stepStatusKey(phase, step));
  const icon = stepIcon(step, action !== 'none', theme);
  // Shown in the branch time zone when the booking could be read (the app's rule for appointment times).
  const whenIso = appointment?.scheduled_at ?? step.scheduled_at;
  const when = action === 'appointment' && whenIso ? formatDateTime(whenIso, language, appointment?.timezone) : null;

  return (
    <View style={{ gap: theme.space(2) }} testID={`step-${step.id}`}>
      <View style={{ flexDirection: 'row', gap: theme.space(3), alignItems: 'flex-start' }} accessible accessibilityLabel={`${label}, ${status}${when ? `, ${t('journey.scheduledFor', { when })}` : ''}`}>
        <Ionicons name={icon.name} size={22} color={icon.color} style={{ marginTop: 1 }} />
        <View style={{ flex: 1, gap: 2 }}>
          <AppText variant="label" style={{ fontSize: theme.font.body, textDecorationLine: step.status === 'completed' ? 'line-through' : 'none' }}>
            {label}
          </AppText>
          <AppText variant="small" style={{ color: icon.color, fontWeight: '600' }} testID={`step-status-${step.id}`}>
            {status}
          </AppText>
          {when ? <AppText variant="small" muted>{t('journey.scheduledFor', { when })}</AppText> : null}
          {appointment && when ? <AppText variant="caption" muted>{appointment.timezone}</AppText> : null}
          {step.status === 'blocked' ? <AppText variant="small" muted>{t('journey.blockedHint')}</AppText> : null}
        </View>
      </View>

      {action === 'intake' ? <Button label={t('journey.action.intake')} icon="options-outline" onPress={handlers.onIntake} testID={`step-intake-${step.id}`} /> : null}
      {action === 'book' ? (
        <>
          <Button label={t('journey.action.book')} icon="calendar-outline" onPress={() => handlers.onBook(step)} testID={`step-book-${step.id}`} />
          <Button kind="secondary" label={t('journey.action.concierge')} icon="chatbubbles-outline" onPress={handlers.onConcierge} testID={`step-concierge-${step.id}`} />
        </>
      ) : null}
      {action === 'book' || action === 'review' ? (
        <Button kind="link" label={t('journey.action.markDone')} onPress={() => handlers.onMarkDone(step)} busy={busy} testID={`step-done-${step.id}`} />
      ) : null}
      {action === 'appointment' && step.appointment_id ? (
        <Button kind="secondary" label={t('journey.action.viewAppointment')} icon="calendar-outline" onPress={() => handlers.onAppointment(step.appointment_id!)} testID={`step-appointment-${step.id}`} />
      ) : null}
      {step.status === 'blocked' && phase.status === 'in_progress' ? (
        <Button kind="secondary" label={t('journey.action.concierge')} icon="chatbubbles-outline" onPress={handlers.onConcierge} testID={`step-concierge-${step.id}`} />
      ) : null}
    </View>
  );
}
