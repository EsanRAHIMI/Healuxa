import * as SecureStore from 'expo-secure-store';

/**
 * Secure persistence for the session. Backed by the iOS Keychain and the Android Keystore
 * (expo-secure-store). Items are bound to this device and only readable while it is unlocked;
 * they are never written to AsyncStorage, files, or logs.
 */
export interface SecureKV {
  getItemAsync(key: string, options?: SecureStore.SecureStoreOptions): Promise<string | null>;
  setItemAsync(key: string, value: string, options?: SecureStore.SecureStoreOptions): Promise<void>;
  deleteItemAsync(key: string, options?: SecureStore.SecureStoreOptions): Promise<void>;
}

export interface StoredSession {
  accessToken: string;
  /** epoch ms */
  accessExpiresAt: number;
  refreshToken: string;
  identifier: string;
}

const KEY = {
  access: 'healuxa.session.access',
  accessExp: 'healuxa.session.access_exp',
  refresh: 'healuxa.session.refresh',
  identifier: 'healuxa.session.identifier',
  biometric: 'healuxa.settings.biometric_lock',
} as const;

const OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export class TokenStore {
  constructor(private readonly kv: SecureKV = SecureStore) {}

  async load(): Promise<StoredSession | null> {
    const [accessToken, exp, refreshToken, identifier] = await Promise.all([
      this.kv.getItemAsync(KEY.access, OPTIONS),
      this.kv.getItemAsync(KEY.accessExp, OPTIONS),
      this.kv.getItemAsync(KEY.refresh, OPTIONS),
      this.kv.getItemAsync(KEY.identifier, OPTIONS),
    ]);
    if (!refreshToken || !accessToken) return null;
    return {
      accessToken,
      accessExpiresAt: Number(exp ?? 0) || 0,
      refreshToken,
      identifier: identifier ?? '',
    };
  }

  async save(session: StoredSession): Promise<void> {
    // Refresh token first: if the app dies mid-write we still hold the newest rotation.
    await this.kv.setItemAsync(KEY.refresh, session.refreshToken, OPTIONS);
    await this.kv.setItemAsync(KEY.access, session.accessToken, OPTIONS);
    await this.kv.setItemAsync(KEY.accessExp, String(session.accessExpiresAt), OPTIONS);
    await this.kv.setItemAsync(KEY.identifier, session.identifier, OPTIONS);
  }

  async clear(): Promise<void> {
    await Promise.all(
      [KEY.access, KEY.accessExp, KEY.refresh, KEY.identifier].map((k) => this.kv.deleteItemAsync(k, OPTIONS))
    );
  }

  async getBiometricLock(): Promise<boolean> {
    return (await this.kv.getItemAsync(KEY.biometric, OPTIONS)) === '1';
  }

  async setBiometricLock(enabled: boolean): Promise<void> {
    if (enabled) await this.kv.setItemAsync(KEY.biometric, '1', OPTIONS);
    else await this.kv.deleteItemAsync(KEY.biometric, OPTIONS);
  }
}

export const STORE_KEYS = KEY;
