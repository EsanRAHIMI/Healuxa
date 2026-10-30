import { ApiError } from '../api/errors';
import { SessionManager } from '../auth/sessionManager';
import { STORE_KEYS, TokenStore } from '../auth/tokenStore';
import { fakeIdentity, fakeSecureKV, tokens } from '../testing/helpers';

function setup(identity = fakeIdentity(), now = () => 1_000_000) {
  const secure = fakeSecureKV();
  const store = new TokenStore(secure.kv);
  const manager = new SessionManager(identity, store, now);
  return { identity, secure, store, manager };
}

describe('SessionManager auth flow', () => {
  it('signs in, persists tokens in the secure store and exposes claims', async () => {
    const { manager, secure, identity } = setup();
    const events: (string | undefined)[] = [];
    manager.subscribe((s) => events.push(s?.identifier));
    await manager.signIn('  Person@Example.test ', 'correct-horse');
    expect(identity.login).toHaveBeenCalledWith({ identifier: 'Person@Example.test', password: 'correct-horse' });
    expect(secure.items.get(STORE_KEYS.refresh)).toBe('refresh-1');
    expect(secure.items.get(STORE_KEYS.identifier)).toBe('person@example.test');
    expect(manager.claims).toMatchObject({ sub: 'U1', session_id: 'S1' });
    expect(events).toEqual(['person@example.test']);
  });

  it('registers with the idempotency key and locale', async () => {
    const { manager, identity } = setup();
    await manager.register('new@example.test', 'longenough', 'ar', 'idem-key-123');
    expect(identity.register).toHaveBeenCalledWith(
      { identifier: 'new@example.test', password: 'longenough', locale: 'ar' },
      'idem-key-123'
    );
    expect(manager.current?.refreshToken).toBe('refresh-1');
  });

  it('rotates the refresh token and persists the new one', async () => {
    const { manager, secure, identity } = setup();
    await manager.signIn('a@example.test', 'pw-123456');
    await manager.refresh();
    expect(identity.refresh).toHaveBeenCalledWith('refresh-1');
    expect(secure.items.get(STORE_KEYS.refresh)).toBe('refresh-2');
  });

  it('shares one in-flight refresh between concurrent callers', async () => {
    let resolve!: (v: ReturnType<typeof tokens>) => void;
    const identity = fakeIdentity({ refresh: jest.fn(() => new Promise((r) => (resolve = r))) });
    const { manager } = setup(identity);
    await manager.signIn('a@example.test', 'pw-123456');
    const a = manager.refresh();
    const b = manager.refresh();
    resolve(tokens(2));
    await Promise.all([a, b]);
    expect(identity.refresh).toHaveBeenCalledTimes(1);
  });

  it('refreshes proactively when the access token is about to expire', async () => {
    let now = 1_000_000;
    const { manager, identity } = setup(fakeIdentity(), () => now);
    await manager.signIn('a@example.test', 'pw-123456');
    now += 899_000; // 1s before expiry, inside the 60s skew
    await manager.accessToken();
    expect(identity.refresh).toHaveBeenCalledTimes(1);
  });

  it('retries an authenticated call once after a 401', async () => {
    const { manager } = setup();
    await manager.signIn('a@example.test', 'pw-123456');
    const call = jest
      .fn()
      .mockRejectedValueOnce(new ApiError({ status: 401, code: 'unauthorized' }))
      .mockResolvedValueOnce('ok');
    await expect(manager.withAuth(call)).resolves.toBe('ok');
    expect(call).toHaveBeenCalledTimes(2);
    expect(call.mock.calls[1][0]).toBe(tokens(2).access_token);
  });

  it('ends the session when the refresh token is rejected (rotation reuse / revoked)', async () => {
    const identity = fakeIdentity({ refresh: jest.fn(async () => { throw new ApiError({ status: 401, code: 'unauthorized' }); }) });
    const { manager, secure } = setup(identity);
    const reasons: (string | undefined)[] = [];
    await manager.signIn('a@example.test', 'pw-123456');
    manager.subscribe((_s, reason) => reasons.push(reason));
    await expect(manager.refresh()).rejects.toMatchObject({ status: 401 });
    expect(manager.current).toBeNull();
    expect(secure.items.size).toBe(0);
    expect(reasons).toEqual(['expired']);
  });

  it('keeps the session when refresh fails because the network is down', async () => {
    const identity = fakeIdentity({ refresh: jest.fn(async () => { throw new ApiError({ status: 0, code: 'network_error' }); }) });
    const { manager } = setup(identity);
    await manager.signIn('a@example.test', 'pw-123456');
    await expect(manager.refresh()).rejects.toMatchObject({ code: 'network_error' });
    expect(manager.current).not.toBeNull();
  });

  it('signs out: revokes server-side and clears local storage', async () => {
    const { manager, secure, identity } = setup();
    await manager.signIn('a@example.test', 'pw-123456');
    await expect(manager.signOut()).resolves.toBe(true);
    expect(identity.logout).toHaveBeenCalledWith(tokens(1).access_token);
    expect(secure.items.size).toBe(0);
  });

  it('signs out locally and reports when the server could not be reached', async () => {
    const identity = fakeIdentity({ logout: jest.fn(async () => { throw new ApiError({ status: 0, code: 'network_error' }); }) });
    const { manager, secure } = setup(identity);
    await manager.signIn('a@example.test', 'pw-123456');
    await expect(manager.signOut()).resolves.toBe(false);
    expect(manager.current).toBeNull();
    expect(secure.items.size).toBe(0);
  });

  it('restores a persisted session after restart', async () => {
    const first = setup();
    await first.manager.signIn('a@example.test', 'pw-123456');
    const second = new SessionManager(fakeIdentity(), new TokenStore(first.secure.kv));
    await expect(second.restore()).resolves.toMatchObject({ refreshToken: 'refresh-1', identifier: 'a@example.test' });
  });
});
