import { createApiClient } from '../api/client';
import { ApiError } from '../api/errors';
import { PublicCache } from '../cache/publicCache';
import { loadJourneyPlan, loadJourneySummary } from '../journey/load';
import { createMemoryStore } from '../storage/fileStore';
import { jsonResponse } from '../testing/helpers';

type Call = { url: string; method?: string; headers: Record<string, string>; body: unknown };

function clientWith(respond: (url: string, init?: RequestInit) => Response) {
  const calls: Call[] = [];
  const store = createMemoryStore();
  const client = createApiClient({
    identityBaseUrl: 'http://i',
    providerBaseUrl: 'http://p',
    appointmentBaseUrl: 'http://a',
    journeyBaseUrl: 'http://j',
    assessmentBaseUrl: 'http://s',
    cache: new PublicCache(store),
    fetch: async (url, init) => {
      calls.push({
        url,
        method: init?.method,
        headers: (init?.headers ?? {}) as Record<string, string>,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      });
      return respond(url, init);
    },
  });
  return { client, calls, store };
}

const journey = { id: 'J1', user_id: 'U1', primary_goals: ['skin_health'], status: 'onboarding' };
const problem = (status: number, code: string) => jsonResponse(status, { code, title: code, status, trace_id: 't' });

describe('journey client', () => {
  it('creates a journey with the goals in order and an idempotency key', async () => {
    const { client, calls } = clientWith(() => jsonResponse(201, journey));
    await expect(client.journeys.create('tok', { user_id: 'U1', primary_goals: ['skin_health', 'longevity'] }, 'key-1')).resolves.toEqual(journey);
    expect(calls[0]).toMatchObject({
      url: 'http://j/v1/journeys',
      method: 'POST',
      body: { user_id: 'U1', primary_goals: ['skin_health', 'longevity'] },
    });
    expect(calls[0]!.headers['Idempotency-Key']).toBe('key-1');
    expect(calls[0]!.headers.Authorization).toBe('Bearer tok');
  });

  it('surfaces 409 (already has an active journey) and 422 (bad goals) as errors', async () => {
    const conflict = clientWith(() => problem(409, 'conflict'));
    await expect(conflict.client.journeys.create('tok', { user_id: 'U1', primary_goals: ['longevity'] }, 'k')).rejects.toMatchObject({ status: 409, code: 'conflict' });
    const invalid = clientWith(() => problem(422, 'validation_error'));
    await expect(invalid.client.journeys.create('tok', { user_id: 'U1', primary_goals: [] }, 'k')).rejects.toMatchObject({ status: 422 });
  });

  it('treats 404 from the active-journey lookup as "no journey yet"', async () => {
    const { client, calls } = clientWith(() => problem(404, 'not_found'));
    await expect(client.journeys.getActive('tok', 'U1')).resolves.toBeNull();
    expect(calls[0]!.url).toBe('http://j/v1/journeys/U1');
  });

  it('does not hide other failures of the active-journey lookup', async () => {
    const down = clientWith(() => problem(503, 'service_unavailable'));
    await expect(down.client.journeys.getActive('tok', 'U1')).rejects.toBeInstanceOf(ApiError);
    const expired = clientWith(() => problem(401, 'unauthorized'));
    await expect(expired.client.journeys.getActive('tok', 'U1')).rejects.toMatchObject({ code: 'unauthorized' });
  });

  it('reads the roadmap and next actions of a journey', async () => {
    const { client, calls } = clientWith((url) => (url.endsWith('/roadmap') ? jsonResponse(200, { journey_id: 'J1', phases: [] }) : jsonResponse(200, [])));
    await expect(client.journeys.roadmap('tok', 'J1')).resolves.toEqual({ journey_id: 'J1', phases: [] });
    await expect(client.journeys.nextActions('tok', 'J1')).resolves.toEqual([]);
    expect(calls.map((c) => c.url)).toEqual(['http://j/v1/journeys/J1/roadmap', 'http://j/v1/journeys/J1/next-actions']);
  });

  it('completes a step with an idempotency key and closes a journey', async () => {
    const { client, calls } = clientWith((url) => (url.endsWith('/close') ? jsonResponse(200, { ...journey, status: 'churned' }) : jsonResponse(200, { id: 'M1', title: 'x', status: 'completed' })));
    await expect(client.journeys.completeMilestone('tok', 'J1', 'M1', 'key-2')).resolves.toMatchObject({ status: 'completed' });
    await expect(client.journeys.close('tok', 'J1')).resolves.toMatchObject({ status: 'churned' });
    expect(calls[0]).toMatchObject({ url: 'http://j/v1/journeys/J1/milestones/M1/complete', method: 'POST' });
    expect(calls[0]!.headers['Idempotency-Key']).toBe('key-2');
    expect(calls[1]).toMatchObject({ url: 'http://j/v1/journeys/J1/close', method: 'POST' });
  });

  it('starts an intake assessment and submits the responses', async () => {
    const { client, calls } = clientWith(() => jsonResponse(200, { id: 'A1', user_id: 'U1', kind: 'intake', status: 'in_progress' }));
    await client.assessments.startIntake('tok', 'U1', 'key-3');
    await client.assessments.submit('tok', 'A1', [{ question: 'city', answer: 'dubai' }], 'key-4');
    expect(calls[0]).toMatchObject({ url: 'http://s/v1/assessments', method: 'POST', body: { user_id: 'U1', kind: 'intake' } });
    expect(calls[0]!.headers['Idempotency-Key']).toBe('key-3');
    expect(calls[1]).toMatchObject({ url: 'http://s/v1/assessments/A1/submit', method: 'POST', body: { responses: [{ question: 'city', answer: 'dubai' }] } });
    expect(calls[1]!.headers['Idempotency-Key']).toBe('key-4');
  });

  it('never caches journey or assessment responses', async () => {
    const { client, store } = clientWith((url) => (url.endsWith('/roadmap') ? jsonResponse(200, { journey_id: 'J1', phases: [] }) : jsonResponse(200, journey)));
    await client.journeys.getActive('tok', 'U1');
    await client.journeys.roadmap('tok', 'J1');
    expect(store.dump()).toEqual({});
  });

  it('falls back to the gateway base when no per-service URL is configured', async () => {
    const urls: string[] = [];
    const client = createApiClient({
      identityBaseUrl: 'https://api',
      providerBaseUrl: 'https://api',
      fetch: async (url) => {
        urls.push(url);
        return jsonResponse(200, []);
      },
    });
    await client.journeys.nextActions('tok', 'J1');
    await client.assessments.startIntake('tok', 'U1', 'k');
    expect(urls).toEqual(['https://api/v1/journeys/J1/next-actions', 'https://api/v1/assessments']);
  });

  it('booking carries the journey step id only when one is given', async () => {
    const { client, calls } = clientWith(() => jsonResponse(201, { id: 'AP1' }));
    await client.appointments.hold('tok', { service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z', milestone_id: 'M2' }, 'k1');
    await client.appointments.hold('tok', { service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z' }, 'k2');
    expect(calls[0]!.body).toEqual({ service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z', milestone_id: 'M2', channel: 'app' });
    expect(calls[1]!.body).toEqual({ service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z', channel: 'app' });
  });
});

describe('journey loaders', () => {
  it('returns the start state without further calls when there is no journey', async () => {
    const { client, calls } = clientWith(() => problem(404, 'not_found'));
    await expect(loadJourneyPlan(client, 'tok', 'U1')).resolves.toEqual({ journey: null, roadmap: null, appointments: {} });
    await expect(loadJourneySummary(client, 'tok', 'U1')).resolves.toEqual({ journey: null, roadmap: null, nextActions: [] });
    expect(calls).toHaveLength(2);
  });

  it('loads the bookings behind scheduled steps, and still shows the plan if one cannot be read', async () => {
    const roadmap = {
      journey_id: 'J1',
      phases: [
        {
          id: 'P2',
          code: 'consult',
          name: 'Consult',
          sequence: 2,
          status: 'in_progress',
          milestones: [
            { id: 'M2', title: 'Consultation', status: 'scheduled', code: 'consultation', appointment_id: 'AP1', scheduled_at: '2026-12-01T05:00:00Z' },
            { id: 'M3', title: 'Consultation', status: 'scheduled', code: 'consultation', appointment_id: 'AP2', scheduled_at: '2026-12-02T05:00:00Z' },
          ],
        },
      ],
    };
    const { client } = clientWith((url) => {
      if (url === 'http://j/v1/journeys/U1') return jsonResponse(200, journey);
      if (url.endsWith('/roadmap')) return jsonResponse(200, roadmap);
      if (url === 'http://a/v1/appointments/AP1') return jsonResponse(200, { id: 'AP1', timezone: 'Asia/Dubai' });
      return problem(500, 'internal_error');
    });
    const plan = await loadJourneyPlan(client, 'tok', 'U1');
    expect(plan.roadmap).toEqual(roadmap);
    expect(plan.appointments).toEqual({ AP1: { id: 'AP1', timezone: 'Asia/Dubai' } });
  });
});
