import "server-only";

import { NotFoundError, unwrap, type Journey, type JourneyMilestone, type RoadmapPhase } from "@healuxa/api-client";

import { userApi } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { ULID } from "@/lib/journey";

export interface JourneyView {
  journey: Journey;
  phases: RoadmapPhase[];
}

/** The signed-in customer's active journey with its roadmap, or null when they have none. */
export async function loadJourney(userId: string): Promise<JourneyView | null> {
  const api = await userApi();
  const journey = await unwrap(api.transformation.GET("/journeys/{userId}", { params: { path: { userId } } })).catch((e) => {
    if (e instanceof NotFoundError) return null;
    throw e;
  });
  if (!journey?.id) return null;
  const roadmap = await unwrap(api.transformation.GET("/journeys/{id}/roadmap", { params: { path: { id: journey.id } } }));
  return { journey, phases: roadmap.phases ?? [] };
}

/**
 * Resolve a `?milestone=` query value to one of the caller's own open steps. Anything else (signed
 * out, malformed, someone else's, already completed, service unavailable) yields null so a booking
 * is simply made without a journey link rather than failing.
 */
export async function findOpenStep(milestoneId: string | undefined): Promise<JourneyMilestone | null> {
  if (!milestoneId || !ULID.test(milestoneId)) return null;
  const session = await getSession();
  if (!session) return null;
  try {
    const view = await loadJourney(session.userId);
    const step = view?.phases.flatMap((p) => p.milestones).find((m) => m.id === milestoneId);
    return step && step.status !== "completed" ? step : null;
  } catch {
    return null;
  }
}
