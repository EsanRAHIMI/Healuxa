"use server";

/**
 * Journey mutations (transformation-engine, assessment-service).
 * Flow: choose goals -> journey with a generated plan -> intake preferences (assessment kind
 * `intake`, whose completion event opens the consult stage) -> steps are booked through the normal
 * booking flow carrying `milestone_id`, and follow the appointment's lifecycle from then on.
 */
import { idempotencyHeader, unwrap } from "@healuxa/api-client";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";
import { INTAKE_NOTES_MAX, INTAKE_QUESTIONS, MAX_GOALS, ULID, isGoalCode } from "@/lib/journey";

export async function startJourneyAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(
    fd,
    async (locale) => {
      const session = await actionSession();
      const goals = [...new Set(fd.getAll("goals").filter((v): v is string => typeof v === "string"))].filter(isGoalCode);
      if (goals.length < 1 || goals.length > MAX_GOALS) return invalid(locale, { goals: getT(locale)("journey.errGoals") });
      const api = await userApi();
      await unwrap(
        api.transformation.POST("/journeys", {
          params: { header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
          body: { user_id: session.userId, primary_goals: goals },
        }),
      );
      target = `/${locale}/journey/intake`;
    },
    (locale) => ({ conflict: getT(locale)("journey.alreadyActive") }),
  );
  if (state.ok && target) redirect(target);
  return state;
}

export async function submitIntakeAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    const session = await actionSession();
    const t = getT(locale);
    const errors: Record<string, string> = {};
    const responses: { question: string; answer: string }[] = [];
    for (const q of INTAKE_QUESTIONS) {
      const answer = str(fd, q.code);
      if (!(q.options as readonly string[]).includes(answer)) errors[q.code] = t("journey.intake.errRequired");
      else responses.push({ question: q.code, answer });
    }
    if (Object.keys(errors).length) return invalid(locale, errors);
    const notes = str(fd, "notes").slice(0, INTAKE_NOTES_MAX);
    if (notes) responses.push({ question: "notes", answer: notes });

    const api = await userApi();
    const key = str(fd, "idempotency_key");
    const assessment = await unwrap(
      api.assessment.POST("/assessments", {
        params: { header: idempotencyHeader(key ? `${key}-start` : undefined) },
        body: { user_id: session.userId, kind: "intake" },
      }),
    );
    await unwrap(
      api.assessment.POST("/assessments/{id}/submit", {
        params: { path: { id: assessment.id! }, header: idempotencyHeader(key ? `${key}-submit` : undefined) },
        body: { responses },
      }),
    );
    target = `/${locale}/journey?updated=1`;
  });
  if (state.ok && target) redirect(target);
  return state;
}

export async function completeStepAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const id = str(fd, "journey_id");
    const milestoneId = str(fd, "milestone_id");
    if (!ULID.test(id) || !ULID.test(milestoneId)) return invalid(locale, { milestone_id: "invalid" });
    const api = await userApi();
    await unwrap(
      api.transformation.POST("/journeys/{id}/milestones/{milestoneId}/complete", {
        params: { path: { id, milestoneId }, header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
      }),
    );
    refresh();
    return getT(locale)("journey.markedDone");
  });
}

export async function closeJourneyAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const id = str(fd, "journey_id");
    if (!ULID.test(id)) return invalid(locale, { journey_id: "invalid" });
    const api = await userApi();
    await unwrap(api.transformation.POST("/journeys/{id}/close", { params: { path: { id } } }));
    target = `/${locale}/journey`;
  });
  if (state.ok && target) redirect(target);
  return state;
}
