/**
 * Pure journey logic shared by the journey screens and the home card. No React, no network.
 *
 * The journey is a coordination plan only: nothing here (or in the copy it selects) recommends a
 * treatment or a test. Names come from `code` (+ goal) so they can be localised on the device.
 */
import { GOAL_CODES, type AssessmentResponse, type GoalCode, type Milestone, type Roadmap, type RoadmapPhase } from '../api/types';
import type { MessageKey } from '../i18n';

export const MAX_GOALS = 3;
export const NOTES_MAX_LENGTH = 1000;

/** Adds or removes a goal, keeping the customer's order of priority; a 4th goal is ignored. */
export function toggleGoal(selected: readonly GoalCode[], goal: GoalCode): GoalCode[] {
  if (selected.includes(goal)) return selected.filter((g) => g !== goal);
  if (selected.length >= MAX_GOALS) return [...selected];
  return [...selected, goal];
}

export const isGoalCode = (v: unknown): v is GoalCode => (GOAL_CODES as readonly unknown[]).includes(v);

const KNOWN_PHASES = new Set(['understand', 'consult', 'care', 'follow_up']);
const KNOWN_STEPS = new Set(['intake_assessment', 'consultation', 'care', 'follow_up', 'progress_review']);
const BOOKABLE = new Set(['consultation', 'care', 'follow_up']);

type Translate = (key: MessageKey, params?: Record<string, string | number>) => string;

/** Localised goal label; an unknown code is shown as-is rather than hidden. */
export function goalLabel(goal: string | null | undefined, t: Translate): string | undefined {
  if (!goal) return undefined;
  return isGoalCode(goal) ? t(`journey.goal.${goal}`) : goal;
}

/** Localised phase name from `code`; falls back to the server name for a code this build does not know. */
export function phaseLabel(phase: Pick<RoadmapPhase, 'code' | 'name'>, t: Translate): string {
  return phase.code && KNOWN_PHASES.has(phase.code) ? t(`journey.phase.${phase.code}` as MessageKey) : phase.name;
}

/** Localised step name from `code` (+ goal label); falls back to the server title for an unknown code. */
export function stepLabel(step: { code?: string | null; goal?: string | null; title?: string }, t: Translate): string {
  const base = step.code && KNOWN_STEPS.has(step.code) ? t(`journey.step.${step.code}` as MessageKey) : step.title ?? '';
  const goal = goalLabel(step.goal, t);
  return goal ? `${base} · ${goal}` : base;
}

export const sortedPhases = (roadmap: Roadmap | null | undefined): RoadmapPhase[] =>
  [...(roadmap?.phases ?? [])].sort((a, b) => a.sequence - b.sequence);

export const sortedSteps = (phase: RoadmapPhase): Milestone[] =>
  [...phase.milestones].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));

export function progress(roadmap: Roadmap | null | undefined): { done: number; total: number } {
  const steps = (roadmap?.phases ?? []).flatMap((p) => p.milestones);
  return { done: steps.filter((m) => m.status === 'completed').length, total: steps.length };
}

export const currentPhase = (roadmap: Roadmap | null | undefined): RoadmapPhase | undefined =>
  sortedPhases(roadmap).find((p) => p.status === 'in_progress');

export function intakeCompleted(roadmap: Roadmap | null | undefined): boolean {
  const intake = (roadmap?.phases ?? []).flatMap((p) => p.milestones).filter((m) => m.code === 'intake_assessment');
  return intake.length > 0 && intake.every((m) => m.status === 'completed');
}

/**
 * What the customer can do with a step right now.
 *   intake      open the preferences form
 *   book        browse services in the step's category (the step id travels to the booking)
 *   review      nothing to book; can only be marked as done
 *   appointment the step is tied to a booking: show its date and link to it
 *   none        completed, on hold, or in a phase that has not started yet
 */
export type StepAction = 'intake' | 'book' | 'review' | 'appointment' | 'none';

export function stepAction(phase: Pick<RoadmapPhase, 'status'>, step: Milestone): StepAction {
  if (step.status === 'completed') return 'none';
  if (step.appointment_id && (step.status === 'scheduled' || step.status === 'in_progress')) return 'appointment';
  if (phase.status !== 'in_progress' || step.status !== 'pending') return 'none';
  if (step.code === 'intake_assessment') return 'intake';
  if (step.code && BOOKABLE.has(step.code)) return 'book';
  if (step.code === 'progress_review') return 'review';
  return 'none';
}

/** Status label for a step; a pending step in a phase that has not started reads as "later". */
export function stepStatusKey(phase: Pick<RoadmapPhase, 'status'>, step: Milestone): MessageKey {
  if (step.status === 'pending' && phase.status !== 'in_progress') return 'journey.stepStatus.upcoming';
  return `journey.stepStatus.${step.status}` as MessageKey;
}

// intake preferences -------------------------------------------------------------
/** Question codes and answer values are shared with the web app: do not rename them. */
export const INTAKE_OPTIONS = {
  timeframe: ['asap', 'within_month', 'within_three_months', 'flexible'],
  city: ['dubai', 'abu_dhabi', 'sharjah', 'other'],
  language: ['en', 'ar', 'fa'],
  practitioner_gender: ['no_preference', 'female', 'male'],
  visit_mode: ['in_person', 'home_visit', 'no_preference'],
} as const;

export type IntakeQuestion = keyof typeof INTAKE_OPTIONS;
export const INTAKE_QUESTIONS = Object.keys(INTAKE_OPTIONS) as IntakeQuestion[];
export type IntakeAnswers = { [Q in IntakeQuestion]?: (typeof INTAKE_OPTIONS)[Q][number] };

export const intakeComplete = (answers: IntakeAnswers): boolean => INTAKE_QUESTIONS.every((q) => Boolean(answers[q]));

/** Responses in the stored shape; empty notes are omitted, long notes are cut at the server limit. */
export function buildIntakeResponses(answers: IntakeAnswers, notes: string): AssessmentResponse[] {
  const responses: AssessmentResponse[] = [];
  for (const question of INTAKE_QUESTIONS) {
    const answer = answers[question];
    if (answer) responses.push({ question, answer });
  }
  const trimmed = notes.trim().slice(0, NOTES_MAX_LENGTH);
  if (trimmed) responses.push({ question: 'notes', answer: trimmed });
  return responses;
}
