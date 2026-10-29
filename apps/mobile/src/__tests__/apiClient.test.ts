import { createApiClient } from '../api/client';
import { ApiError, parseErrorBody } from '../api/errors';
import { request } from '../api/http';
import { isCacheablePublicPath, PublicCache } from '../cache/publicCache';
import { createMemoryStore } from '../storage/fileStore';
import { jsonResponse } from '../testing/helpers';

describe('error states', () => {
  it('parses RFC 9457 problem details', () => {
    const e = parseErrorBody(409, { code: 'conflict', title: 'Conflict', status: 409, trace_id: 't-1', detail: 'Identifier already registered' });
    expect(e).toMatchObject({ status: 409, code: 'conflict', traceId: 't-1', detail: 'Identifier already registered' });
  });

  it('parses FastAPI-wrapped problem details', () => {
    const e = parseErrorBody(401, { detail: { code: 'unauthorized', title: 'Unauthorized', status: 401, trace_id: 't-2' } });
    expect(e).toMatchObject({ code: 'unauthorized', traceId: 't-2' });
  });

  it('parses request validation errors into field errors', () => {
    const e = parseErrorBody(422, { detail: [{ loc: ['body', 'password'], msg: 'too short', type: 'string_too_short' }] });
    expect(e.code).toBe('validation_error');
    expect(e.fieldErrors).toEqual([{ field: 'password', code: 'string_too_short', message: 'too short' }]);
  });

  it('maps unknown bodies by status', () => {
    expect(parseErrorBody(503, 'oops').code).toBe('service_unavailable');
    expect(parseErrorBody(500, undefined).code).toBe('internal_error');
  });

  it('turns fetch failures into network errors', async () => {
    const f = jest.fn(async () => {
      throw new TypeError('Network request failed');
    });
    await expect(request(f, 'http://x', '/v1/providers')).rejects.toMatchObject({ code: 'network_error', status: 0 });
  });

  it('sends bearer token and JSON body', async () => {
    const f = jest.fn(async (_url: string, _init?: RequestInit) => jsonResponse(204));
    await request(f, 'https://api', '/v1/auth/logout', { method: 'POST', accessToken: 'tok', body: { a: 1 } });
    const init = f.mock.calls[0]![1]!;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(init.body).toBe('{"a":1}');
  });
});

describe('public directory cache', () => {
  it('only accepts public directory paths and never authenticated responses', () => {
    expect(isCacheablePublicPath('/v1/providers?limit=3', false)).toBe(true);
    expect(isCacheablePublicPath('/v1/services?provider_id=1', false)).toBe(true);
    expect(isCacheablePublicPath('/v1/providers?limit=3', true)).toBe(false);
    expect(isCacheablePublicPath('/v1/providers/me', false)).toBe(false);
    expect(isCacheablePublicPath('/v1/sessions', false)).toBe(false);
    expect(isCacheablePublicPath('/v1/profiles/U1', false)).toBe(false);
    expect(isCacheablePublicPath('/v1/assessments', false)).toBe(false);
  });

  it('refuses to store non-public content', async () => {
    const cache = new PublicCache(createMemoryStore());
    await expect(cache.put('/v1/sessions', {})).rejects.toThrow(/non-public/);
  });

  it('falls back to cached public content when offline, and flags it', async () => {
    const store = createMemoryStore();
    const cache = new PublicCache(store, 1000, () => 5000);
    const page = { data: [{ id: 'P1' }], page: { limit: 20, has_more: false } };
    const online = jest.fn(async () => jsonResponse(200, page));
    const client = createApiClient({ identityBaseUrl: 'http://i', providerBaseUrl: 'http://p', fetch: online, cache });
    await expect(client.directory.searchProviders({ limit: 20 })).resolves.toEqual({ data: page, fromCache: false });

    const offline = createApiClient({
      identityBaseUrl: 'http://i',
      providerBaseUrl: 'http://p',
      fetch: async () => {
        throw new TypeError('Network request failed');
      },
      cache,
    });
    await expect(offline.directory.searchProviders({ limit: 20 })).resolves.toEqual({ data: page, fromCache: true, storedAt: 5000 });
  });

  it('does not mask server errors with cached data', async () => {
    const cache = new PublicCache(createMemoryStore());
    await cache.put('/v1/providers/P1', { id: 'P1' });
    const client = createApiClient({
      identityBaseUrl: 'http://i',
      providerBaseUrl: 'http://p',
      fetch: async () => jsonResponse(404, { code: 'not_found', title: 'Not found', status: 404, trace_id: 't' }),
      cache,
    });
    await expect(client.directory.getProvider('P1')).rejects.toBeInstanceOf(ApiError);
  });

  it('identity calls are never cached', async () => {
    const store = createMemoryStore();
    const client = createApiClient({
      identityBaseUrl: 'http://i',
      providerBaseUrl: 'http://p',
      fetch: async () => jsonResponse(200, { data: [{ id: 'S1' }], page: { limit: 50, has_more: false } }),
      cache: new PublicCache(store),
    });
    await client.identity.listSessions('tok');
    expect(store.dump()).toEqual({});
  });
});
