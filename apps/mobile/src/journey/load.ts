import type { ApiClient } from '../api/client';
import type { Appointment, Journey, NextAction, Roadmap } from '../api/types';

export interface JourneyPlan {
  /** null when the customer has no active journey yet */
  journey: Journey | null;
  roadmap: Roadmap | null;
  /** bookings behind scheduled steps, by appointment id (for the branch time zone of the date shown) */
  appointments: Record<string, Appointment>;
}

/** transformation: getJourneyByUser → getRoadmap, plus appointment: getAppointment per booked step. */
export async function loadJourneyPlan(api: ApiClient, token: string, userId: string): Promise<JourneyPlan> {
  const journey = await api.journeys.getActive(token, userId);
  if (!journey) return { journey: null, roadmap: null, appointments: {} };
  const roadmap = await api.journeys.roadmap(token, journey.id);
  const ids = roadmap.phases
    .flatMap((p) => p.milestones)
    .filter((m) => m.appointment_id && m.status !== 'completed')
    .map((m) => m.appointment_id!);
  const appointments: Record<string, Appointment> = {};
  // A booking that cannot be read must not hide the plan: the step then shows its own date.
  await Promise.all(
    Array.from(new Set(ids)).map(async (id) => {
      try {
        appointments[id] = await api.appointments.get(token, id);
      } catch {
        /* shown without the booking's time zone */
      }
    })
  );
  return { journey, roadmap, appointments };
}

export interface JourneySummary {
  journey: Journey | null;
  roadmap: Roadmap | null;
  nextActions: NextAction[];
}

/** Home card: transformation: getJourneyByUser → getRoadmap + getNextActions. */
export async function loadJourneySummary(api: ApiClient, token: string, userId: string): Promise<JourneySummary> {
  const journey = await api.journeys.getActive(token, userId);
  if (!journey) return { journey: null, roadmap: null, nextActions: [] };
  const [roadmap, nextActions] = await Promise.all([api.journeys.roadmap(token, journey.id), api.journeys.nextActions(token, journey.id)]);
  return { journey, roadmap, nextActions };
}
