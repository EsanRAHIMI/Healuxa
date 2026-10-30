import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';

import type { Locale } from '../api/types';
import type { Biometrics } from './biometrics';
import type { SessionManager } from './sessionManager';
import type { StoredSession, TokenStore } from './tokenStore';

export type AuthStatus = 'booting' | 'locked' | 'signedOut' | 'signedIn';

export interface AuthValue {
  status: AuthStatus;
  session: StoredSession | null;
  userId?: string;
  sessionId?: string;
  /** set when the backend ended the session (refresh rejected) */
  expired: boolean;
  biometricLock: boolean;
  signIn(identifier: string, password: string): Promise<void>;
  register(identifier: string, password: string, locale: Locale, idempotencyKey: string): Promise<void>;
  /** resolves false if the server could not confirm revocation */
  signOut(): Promise<boolean>;
  unlock(prompt: string, cancelLabel: string): Promise<boolean>;
  setBiometricLock(enabled: boolean, prompt: string, cancelLabel: string): Promise<boolean>;
  withAuth<T>(call: (accessToken: string) => Promise<T>): Promise<T>;
  /** identity: authDeleteAccount; resolves once the account is gone and local state is wiped */
  deleteAccount(password: string): Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

/** Re-lock after the app was in the background this long (biometric lock only). */
const RELOCK_AFTER_MS = 60_000;

export function AuthProvider({
  manager,
  tokenStore,
  biometrics,
  children,
}: {
  manager: SessionManager;
  tokenStore: TokenStore;
  biometrics: Biometrics;
  children: ReactNode;
}) {
  const [status, setStatus] = useState<AuthStatus>('booting');
  const [session, setSession] = useState<StoredSession | null>(null);
  const [expired, setExpired] = useState(false);
  const [biometricLock, setLock] = useState(false);
  const backgroundAt = useRef<number | null>(null);

  useEffect(() => {
    const unsubscribe = manager.subscribe((s, reason) => {
      setSession(s);
      if (s) {
        setExpired(false);
        setStatus('signedIn');
      } else {
        setExpired(reason === 'expired');
        setStatus('signedOut');
      }
    });
    (async () => {
      const lock = await tokenStore.getBiometricLock();
      setLock(lock);
      if (lock) setStatus('locked');
      else if (!(await manager.restore())) setStatus('signedOut');
    })().catch(() => setStatus('signedOut'));
    return () => {
      unsubscribe();
    };
  }, [manager, tokenStore]);

  // Biometric lock: hide the session again when the app returns after a while in the background.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'background') backgroundAt.current = Date.now();
      if (next === 'active' && backgroundAt.current !== null) {
        const away = Date.now() - backgroundAt.current;
        backgroundAt.current = null;
        if (biometricLock && manager.current && away > RELOCK_AFTER_MS) setStatus('locked');
      }
    });
    return () => sub.remove();
  }, [biometricLock, manager]);

  const unlock = useCallback(
    async (prompt: string, cancelLabel: string) => {
      const ok = await biometrics.authenticate(prompt, cancelLabel);
      if (!ok) return false;
      if (manager.current) setStatus('signedIn');
      else if (!(await manager.restore())) setStatus('signedOut');
      return true;
    },
    [biometrics, manager]
  );

  const setBiometricLock = useCallback(
    async (enabled: boolean, prompt: string, cancelLabel: string) => {
      if (enabled) {
        if (!(await biometrics.isAvailable())) return false;
        if (!(await biometrics.authenticate(prompt, cancelLabel))) return false;
      }
      await tokenStore.setBiometricLock(enabled);
      setLock(enabled);
      return true;
    },
    [biometrics, tokenStore]
  );

  const value = useMemo<AuthValue>(() => {
    const claims = manager.claims;
    return {
      status,
      session,
      userId: session ? claims.sub : undefined,
      sessionId: session ? claims.session_id : undefined,
      expired,
      biometricLock,
      signIn: async (identifier, password) => {
        await manager.signIn(identifier, password);
      },
      register: async (identifier, password, locale, key) => {
        await manager.register(identifier, password, locale, key);
      },
      signOut: async () => {
        const ok = await manager.signOut();
        await tokenStore.setBiometricLock(false);
        setLock(false);
        return ok;
      },
      unlock,
      setBiometricLock,
      withAuth: (call) => manager.withAuth(call),
      deleteAccount: async (password) => {
        await manager.deleteAccount(password);
        await tokenStore.setBiometricLock(false);
        await tokenStore.setPushDeviceId(null);
        setLock(false);
      },
    };
  }, [status, session, expired, biometricLock, manager, tokenStore, unlock, setBiometricLock]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(AuthContext);
  if (!v) throw new Error('useAuth must be used inside AuthProvider');
  return v;
}
