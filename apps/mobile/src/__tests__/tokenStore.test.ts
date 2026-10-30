import * as SecureStore from 'expo-secure-store';

import { STORE_KEYS, TokenStore } from '../auth/tokenStore';
import { fakeSecureKV } from '../testing/helpers';

const session = { accessToken: 'a', accessExpiresAt: 123, refreshToken: 'r', identifier: 'x@example.test' };

describe('TokenStore (secure-storage adapter)', () => {
  it('writes every item device-bound and only while unlocked', async () => {
    const { kv, calls } = fakeSecureKV();
    await new TokenStore(kv).save(session);
    expect(calls.filter((c) => c.op === 'set')).toHaveLength(4);
    for (const c of calls) {
      expect(c.options).toEqual({ keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
    }
  });

  it('writes the rotated refresh token before anything else', async () => {
    const { kv, calls } = fakeSecureKV();
    await new TokenStore(kv).save(session);
    expect(calls[0]).toMatchObject({ op: 'set', key: STORE_KEYS.refresh });
  });

  it('round-trips a session', async () => {
    const { kv } = fakeSecureKV();
    const store = new TokenStore(kv);
    await store.save(session);
    await expect(store.load()).resolves.toEqual(session);
  });

  it('treats a missing refresh token as signed out', async () => {
    const { kv, items } = fakeSecureKV();
    items.set(STORE_KEYS.access, 'a');
    await expect(new TokenStore(kv).load()).resolves.toBeNull();
  });

  it('clear() removes every session item but keeps nothing else around', async () => {
    const { kv, items } = fakeSecureKV();
    const store = new TokenStore(kv);
    await store.save(session);
    await store.clear();
    expect(items.size).toBe(0);
  });

  it('stores the biometric-lock preference in the secure store', async () => {
    const { kv, items } = fakeSecureKV();
    const store = new TokenStore(kv);
    await store.setBiometricLock(true);
    expect(items.get(STORE_KEYS.biometric)).toBe('1');
    await expect(store.getBiometricLock()).resolves.toBe(true);
    await store.setBiometricLock(false);
    await expect(store.getBiometricLock()).resolves.toBe(false);
  });

  it('the app never imports AsyncStorage', () => {
    const fs = jest.requireActual<typeof import('fs')>('fs');
    const path = jest.requireActual<typeof import('path')>('path');
    const root = path.join(__dirname, '..', '..');
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (['node_modules', 'ios', 'android', '.expo', '__tests__'].includes(entry.name)) continue;
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (/\.(ts|tsx|js)$/.test(entry.name) && fs.readFileSync(p, 'utf8').includes('@react-native-async-storage')) offenders.push(p);
      }
    };
    walk(path.join(root, 'src'));
    walk(path.join(root, 'app'));
    expect(offenders).toEqual([]);
  });
});
