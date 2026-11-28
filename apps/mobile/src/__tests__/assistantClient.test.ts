import type { AssistantCard } from '../api/assistantTypes';
import { createApiClient } from '../api/client';
import { ApiError } from '../api/errors';
import { cardRoute } from '../assistant/route';
import { jsonResponse } from '../testing/helpers';

type Call = { url: string; method?: string; headers: Record<string, string>; body: unknown };

function clientWith(respond: (url: string) => Response) {
  const calls: Call[] = [];
  const client = createApiClient({
    identityBaseUrl: 'http://i',
    providerBaseUrl: 'http://p',
    aiBaseUrl: 'http://ai',
    fetch: async (url, init) => {
      calls.push({ url, method: init?.method, headers: (init?.headers ?? {}) as Record<string, string>, body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined });
      return respond(url);
    },
  });
  return { client, calls };
}

const SERVICE = '01SERVICE0000000000000001';
const STEP = '01MILESTONE00000000000001';

describe('assistant client', () => {
  it('creates a session in the app language and posts a message with an idempotency key', async () => {
    const { client, calls } = clientWith((url) =>
      url.endsWith('/messages')
        ? jsonResponse(200, { id: 'T1', role: 'assistant', content: 'Here you go.', cards: [], created_at: '2030-01-01T00:00:00Z' })
        : jsonResponse(201, { id: 'S1', locale: 'ar', turns: [], assistant_available: true }),
    );
    await client.assistant.createSession('tok', 'ar');
    const reply = await client.assistant.send('tok', 'S1', 'dental', 'key-1');
    expect(reply.content).toBe('Here you go.');
    expect(calls[0]).toMatchObject({ url: 'http://ai/v1/ai/sessions', method: 'POST', body: { locale: 'ar' } });
    expect(calls[1]).toMatchObject({ url: 'http://ai/v1/ai/sessions/S1/messages', method: 'POST', body: { content: 'dental' } });
    expect(calls[1]!.headers['Idempotency-Key']).toBe('key-1');
    expect(calls[1]!.headers.Authorization).toBe('Bearer tok');
  });

  it('surfaces 503 (no model configured) as an ApiError', async () => {
    const { client } = clientWith(() => jsonResponse(503, { code: 'service_unavailable', title: 'x', status: 503, trace_id: 't' }));
    await expect(client.assistant.send('tok', 'S1', 'hi', 'key-2')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('card routes', () => {
  it('opens the booking screen with the journey step for a service card', () => {
    const card = { kind: 'service', id: SERVICE, milestone_id: STEP, href: '', title: '', category: 'dental', price_type: 'fixed', price: null, next_slots: [] } as AssistantCard;
    expect(cardRoute(card)).toEqual({ pathname: '/book/[serviceId]', params: { serviceId: SERVICE, milestoneId: STEP } });
  });

  it('routes the hand-off to a new concierge request and rejects malformed ids', () => {
    expect(cardRoute({ kind: 'handoff', href: '/account/concierge#new' })).toEqual({ pathname: '/concierge/new' });
    expect(cardRoute({ kind: 'provider', id: '../x', title: null, href: '' })).toBeNull();
  });
});
