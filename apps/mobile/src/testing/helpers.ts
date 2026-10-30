import type { IdentityApi } from '../api/client';
import type { SecureKV } from '../auth/tokenStore';

/** In-memory SecureKV that records the options every call used. */
export function fakeSecureKV() {
  const items = new Map<string, string>();
  const calls: { op: string; key: string; options?: unknown }[] = [];
  const kv: SecureKV = {
    async getItemAsync(key, options) {
      calls.push({ op: 'get', key, options });
      return items.get(key) ?? null;
    },
    async setItemAsync(key, value, options) {
      calls.push({ op: 'set', key, options });
      items.set(key, value);
    },
    async deleteItemAsync(key, options) {
      calls.push({ op: 'delete', key, options });
      items.delete(key);
    },
  };
  return { kv, items, calls };
}

/** Builds an unsigned JWT-shaped token carrying the given claims (for claim parsing only). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const enc = (o: unknown) => Buffer.from(JSON.stringify(o)).toString('base64url');
  return `${enc({ alg: 'none' })}.${enc(claims)}.sig`;
}

export function tokens(n: number, sessionId = 'S1') {
  return {
    access_token: fakeJwt({ sub: 'U1', session_id: sessionId, n }),
    refresh_token: `refresh-${n}`,
    token_type: 'Bearer' as const,
    expires_in: 900,
  };
}

export function fakeIdentity(overrides: Partial<IdentityApi> = {}): jest.Mocked<IdentityApi> {
  return {
    register: jest.fn(async () => tokens(1)),
    login: jest.fn(async () => tokens(1)),
    refresh: jest.fn(async () => tokens(2)),
    logout: jest.fn(async () => undefined),
    listSessions: jest.fn(async () => ({ data: [], page: { limit: 50, has_more: false } })),
    revokeSession: jest.fn(async () => undefined),
    deleteAccount: jest.fn(async () => undefined),
    ...overrides,
  } as jest.Mocked<IdentityApi>;
}

export function jsonResponse(status: number, body?: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  } as unknown as Response;
}
