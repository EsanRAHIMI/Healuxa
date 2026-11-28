/**
 * Wire types for the personalised journey (re-exported by ./types):
 *   transformation.openapi.yaml 3.3.0, assessment.openapi.yaml.
 *
 * A journey is a COORDINATION plan (preferences, consultations, visits, follow-ups). It carries no
 * clinical content; any decision about care belongs to the practitioner.
 */
import type { Money } from './types';

export const GOAL_CODES = [
  'skin_health',
  'facial_aesthetics',
  'hair_restoration',
  'dental_smile',
  'weight_management',
  'fitness_recovery',
  'preventive_checkup',
  'longevity',
  'mental_wellbeing',
] as const;
export type GoalCode = (typeof GOAL_CODES)[number];

export type JourneyStatus = 'draft' | 'onboarding' | 'active' | 'at_risk' | 'renewing' | 'completed' | 'churned';

export interface JourneyCreate {
  user_id: string;
  /** 1–3 unique goals in the customer's order of priority */
  primary_goals: GoalCode[];
}

export interface Journey {
  id: string;
  user_id: string;
  primary_goals: string[];
  status: JourneyStatus;
  health_index?: number;
  started_at?: string;
  ltv_projection?: Money | null;
}

export type PhaseCode = 'understand' | 'consult' | 'care' | 'follow_up';
export type PhaseStatus = 'pending' | 'in_progress' | 'completed';
export type MilestoneCode = 'intake_assessment' | 'consultation' | 'care' | 'follow_up' | 'progress_review';
export type MilestoneStatus = 'pending' | 'scheduled' | 'in_progress' | 'completed' | 'blocked';

/** A plan step. Bookable steps name the provider-catalog `service_category` to book from. */
export interface Milestone {
  id: string;
  /** English, server-side; the app localises from `code` + `goal` instead */
  title: string;
  status: MilestoneStatus;
  due_at?: string | null;
  code?: MilestoneCode | (string & {}) | null;
  goal?: string | null;
  phase_id?: string | null;
  sequence?: number;
  service_category?: string | null;
  appointment_id?: string | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
}

export interface RoadmapPhase {
  id: string;
  code?: PhaseCode | (string & {}) | null;
  /** English, server-side; the app localises from `code` instead */
  name: string;
  sequence: number;
  status: PhaseStatus;
  started_at?: string | null;
  completed_at?: string | null;
  milestones: Milestone[];
}

export interface Roadmap {
  journey_id: string;
  phases: RoadmapPhase[];
}

export interface NextAction {
  action_type: 'book' | 'assess' | 'renew' | 'upsell' | 'adherence' | 'follow_up' | 'contact';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  due_at?: string | null;
  milestone_id?: string | null;
  milestone_code?: string | null;
  goal?: string | null;
  service_category?: string | null;
}

// assessment -------------------------------------------------------------------
export interface AssessmentResponse {
  question: string;
  answer: string;
}

export interface Assessment {
  id: string;
  user_id: string;
  kind: string;
  status: 'in_progress' | 'completed';
  recommended_goals?: string[];
  scores?: Record<string, number>;
}
