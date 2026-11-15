import type { GoalCode, Milestone, Roadmap, RoadmapPhase } from '../api/types';
import { GOAL_CODES } from '../api/types';
import { ar } from '../i18n/ar';
import { en } from '../i18n/en';
import { fa } from '../i18n/fa';
import { type MessageKey, translate } from '../i18n';
import {
  buildIntakeResponses,
  currentPhase,
  goalLabel,
  INTAKE_OPTIONS,
  intakeComplete,
  intakeCompleted,
  MAX_GOALS,
  NOTES_MAX_LENGTH,
  phaseLabel,
  progress,
  sortedPhases,
  stepAction,
  stepLabel,
  stepStatusKey,
  toggleGoal,
} from '../journey/plan';

const t = (key: MessageKey, params?: Record<string, string | number>) => translate('en', key, params);
const step = (over: Partial<Milestone>): Milestone => ({ id: 'M', title: 'Server title', status: 'pending', ...over });
const phase = (over: Partial<RoadmapPhase>): RoadmapPhase => ({ id: 'P', name: 'Server name', sequence: 1, status: 'in_progress', milestones: [], ...over });

describe('goal selection', () => {
  it('keeps the order of priority and removes on a second tap', () => {
    let goals: GoalCode[] = [];
    goals = toggleGoal(goals, 'longevity');
    goals = toggleGoal(goals, 'skin_health');
    expect(goals).toEqual(['longevity', 'skin_health']);
    expect(toggleGoal(goals, 'longevity')).toEqual(['skin_health']);
  });

  it('never selects more than three goals', () => {
    const goals = GOAL_CODES.reduce<GoalCode[]>((cur, g) => toggleGoal(cur, g), []);
    expect(goals).toHaveLength(MAX_GOALS);
    expect(goals).toEqual(GOAL_CODES.slice(0, 3));
    expect(new Set(goals).size).toBe(goals.length);
  });
});

describe('localised names', () => {
  it('has a label for every goal in every language, with the agreed English wording', () => {
    expect(GOAL_CODES.map((g) => en[`journey.goal.${g}`])).toEqual([
      'Skin health',
      'Facial aesthetics',
      'Hair restoration',
      'Dental and smile',
      'Weight management',
      'Fitness and recovery',
      'Preventive check-up',
      'Longevity',
      'Mental wellbeing',
    ]);
    for (const g of GOAL_CODES) {
      expect(ar[`journey.goal.${g}`]).toBeTruthy();
      expect(fa[`journey.goal.${g}`]).toBeTruthy();
    }
  });

  it('names phases and steps from their code, not from the English server text', () => {
    expect(phaseLabel(phase({ code: 'follow_up' }), t)).toBe('Follow-up');
    expect(stepLabel(step({ code: 'consultation', goal: 'skin_health' }), t)).toBe('Consultation · Skin health');
    expect(stepLabel(step({ code: 'intake_assessment' }), t)).toBe('Share your preferences');
    expect(stepLabel(step({ code: 'care', goal: 'dental_smile' }), (k, p) => translate('ar', k, p))).toBe(`${ar['journey.step.care']} · ${ar['journey.goal.dental_smile']}`);
  });

  it('falls back to the server text only for codes this build does not know', () => {
    expect(phaseLabel(phase({ code: 'maintenance', name: 'Maintenance' }), t)).toBe('Maintenance');
    expect(stepLabel(step({ code: null, title: 'Custom step' }), t)).toBe('Custom step');
    expect(goalLabel('sleep', t)).toBe('sleep');
  });

  it('has a label for every intake option', () => {
    for (const q of ['timeframe', 'city', 'practitioner_gender', 'visit_mode'] as const) {
      for (const v of INTAKE_OPTIONS[q]) expect(en[`intake.${q}.${v}` as MessageKey]).toBeTruthy();
    }
  });
});

describe('plan state', () => {
  const roadmap: Roadmap = {
    journey_id: 'J1',
    phases: [
      phase({ id: 'P2', code: 'consult', sequence: 2, status: 'in_progress', milestones: [step({ id: 'M2', code: 'consultation' }), step({ id: 'M3', code: 'consultation', status: 'scheduled', appointment_id: 'AP1' })] }),
      phase({ id: 'P1', code: 'understand', sequence: 1, status: 'completed', milestones: [step({ id: 'M1', code: 'intake_assessment', status: 'completed' })] }),
      phase({ id: 'P3', code: 'care', sequence: 3, status: 'pending', milestones: [step({ id: 'M4', code: 'care' })] }),
    ],
  };

  it('orders phases, counts progress and finds the current phase', () => {
    expect(sortedPhases(roadmap).map((p) => p.id)).toEqual(['P1', 'P2', 'P3']);
    expect(progress(roadmap)).toEqual({ done: 1, total: 4 });
    expect(currentPhase(roadmap)?.id).toBe('P2');
    expect(progress(null)).toEqual({ done: 0, total: 0 });
  });

  it('knows when the intake step is completed', () => {
    expect(intakeCompleted(roadmap)).toBe(true);
    expect(intakeCompleted({ journey_id: 'J', phases: [phase({ milestones: [step({ code: 'intake_assessment' })] })] })).toBe(false);
    expect(intakeCompleted(null)).toBe(false);
  });

  it('offers actions only for pending steps of the current phase', () => {
    const current = phase({ status: 'in_progress' });
    expect(stepAction(current, step({ code: 'intake_assessment' }))).toBe('intake');
    expect(stepAction(current, step({ code: 'consultation' }))).toBe('book');
    expect(stepAction(current, step({ code: 'care' }))).toBe('book');
    expect(stepAction(current, step({ code: 'follow_up' }))).toBe('book');
    expect(stepAction(current, step({ code: 'progress_review' }))).toBe('review');
    expect(stepAction(current, step({ code: 'consultation', status: 'completed' }))).toBe('none');
    expect(stepAction(current, step({ code: 'consultation', status: 'blocked' }))).toBe('none');
    expect(stepAction(current, step({ code: 'something_new' }))).toBe('none');
  });

  it('shows later-phase steps without actions', () => {
    const later = phase({ status: 'pending' });
    expect(stepAction(later, step({ code: 'care' }))).toBe('none');
    expect(stepStatusKey(later, step({ code: 'care' }))).toBe('journey.stepStatus.upcoming');
    expect(stepStatusKey(phase({ status: 'in_progress' }), step({ code: 'care' }))).toBe('journey.stepStatus.pending');
  });

  it('links a scheduled step to its booking', () => {
    expect(stepAction(phase({}), step({ status: 'scheduled', appointment_id: 'AP1' }))).toBe('appointment');
    expect(stepAction(phase({}), step({ status: 'scheduled', appointment_id: null }))).toBe('none');
  });
});

describe('intake responses', () => {
  const answers = { timeframe: 'asap', city: 'dubai', language: 'fa', practitioner_gender: 'female', visit_mode: 'home_visit' } as const;

  it('uses the question codes and answer values shared with the web app', () => {
    expect(INTAKE_OPTIONS).toEqual({
      timeframe: ['asap', 'within_month', 'within_three_months', 'flexible'],
      city: ['dubai', 'abu_dhabi', 'sharjah', 'other'],
      language: ['en', 'ar', 'fa'],
      practitioner_gender: ['no_preference', 'female', 'male'],
      visit_mode: ['in_person', 'home_visit', 'no_preference'],
    });
    expect(buildIntakeResponses(answers, '  Ground floor please  ')).toEqual([
      { question: 'timeframe', answer: 'asap' },
      { question: 'city', answer: 'dubai' },
      { question: 'language', answer: 'fa' },
      { question: 'practitioner_gender', answer: 'female' },
      { question: 'visit_mode', answer: 'home_visit' },
      { question: 'notes', answer: 'Ground floor please' },
    ]);
  });

  it('omits empty notes and caps long ones', () => {
    expect(buildIntakeResponses(answers, '   ').some((r) => r.question === 'notes')).toBe(false);
    const long = buildIntakeResponses(answers, 'x'.repeat(NOTES_MAX_LENGTH + 50));
    expect(long.at(-1)!.answer).toHaveLength(NOTES_MAX_LENGTH);
  });

  it('requires every choice question', () => {
    expect(intakeComplete(answers)).toBe(true);
    expect(intakeComplete({ ...answers, city: undefined })).toBe(false);
  });
});
