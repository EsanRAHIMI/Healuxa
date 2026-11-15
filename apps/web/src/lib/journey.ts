/**
 * Journey vocabulary shared by pages and actions. Goal codes mirror GoalCode in
 * transformation.openapi.yaml; intake question codes are stored verbatim by assessment-service and
 * are shared with the mobile app, so do not rename them.
 */
import type { GoalCode, JourneyMilestone } from "@healuxa/api-client";
import type { Translator } from "@healuxa/i18n";

export const GOAL_CODES = [
  "skin_health",
  "facial_aesthetics",
  "hair_restoration",
  "dental_smile",
  "weight_management",
  "fitness_recovery",
  "preventive_checkup",
  "longevity",
  "mental_wellbeing",
] as const satisfies readonly GoalCode[];

export const MAX_GOALS = 3;

export const INTAKE_QUESTIONS = [
  { code: "timeframe", options: ["asap", "within_month", "within_three_months", "flexible"] },
  { code: "city", options: ["dubai", "abu_dhabi", "sharjah", "other"] },
  { code: "language", options: ["en", "ar", "fa"] },
  { code: "practitioner_gender", options: ["no_preference", "female", "male"] },
  { code: "visit_mode", options: ["in_person", "home_visit", "no_preference"] },
] as const;

export const INTAKE_NOTES_MAX = 1000;

export const STEP_CODES = ["intake_assessment", "consultation", "care", "follow_up", "progress_review"] as const;
export const BOOKABLE_STEPS: readonly string[] = ["consultation", "care", "follow_up"];
export const PHASE_CODES = ["understand", "consult", "care", "follow_up"] as const;

export const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;

export function isGoalCode(value: string): value is GoalCode {
  return (GOAL_CODES as readonly string[]).includes(value);
}

/** Localised step name from its code and goal; the API's English title is only a fallback. */
export function stepLabel(t: Translator, step: Pick<JourneyMilestone, "code" | "goal" | "title">): string {
  const code = step.code && (STEP_CODES as readonly string[]).includes(step.code) ? step.code : null;
  if (!code) return step.title ?? t("journey.step.other");
  const goal = step.goal && isGoalCode(step.goal) ? t(`journey.goal.${step.goal}`) : "";
  return t(`journey.step.${code}`, { goal });
}

export function phaseLabel(t: Translator, phase: { code?: string | null; name: string }): string {
  return phase.code && (PHASE_CODES as readonly string[]).includes(phase.code) ? t(`journey.phase.${phase.code}`) : phase.name;
}
