import type { IdentityApi } from '../api/client';
import { ApiError } from '../api/errors';
import type { Locale, TokenResponse } from '../api/types';
import { readClaims } from './jwt';
import type { StoredSession, TokenStore } from './tokenStore';

export type SessionListener = (session: StoredSession | null, reason?: 'expired' | 'signed_out') => void;

/** Refresh this long before the access token expires. */
const EXPIRY_SKEW_MS = 60_000;

/**
 * Owns the signed-in session: persistence (secure store), refresh-token rotation with a single
 * in-flight refresh, authenticated calls with one retry on 401, and sign-out.
 */
export class SessionManager {
  private session: StoredSession | null = null;
  private refreshing: Promise<StoredSession> | null = null;
  private listeners = new Set<SessionListener>();
  /** Server-side cleanup that must run while the session is still valid (e.g. push token removal). */
  private signOutHooks = new Set<(accessToken: string) => Promise<void>>();

  constructor(
    private readonly identity: IdentityApi,
    private readonly store: TokenStore,
    private readonly now: () => number = Date.now
  ) {}

  get current(): StoredSession | null {
    return this.session;
  }

  subscribe(listener: SessionListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(reason?: 'expired' | 'signed_out') {
    for (const l of this.listeners) l(this.session, reason);
  }

  /** Loads the persisted session into memory (call after the optional biometric gate). */
  async restore(): Promise<StoredSession | null> {
    this.session = await this.store.load();
    this.emit();
    return this.session;
  }

  private async establish(tokens: TokenResponse, identifier: string, previousRefresh?: string) {
    const refreshToken = tokens.refresh_token ?? previousRefresh;
    if (!refreshToken) {
      throw new ApiError({ status: 0, code: 'unknown', detail: 'Identity service returned no refresh token' });
    }
    const session: StoredSession = {
      accessToken: tokens.access_token,
      accessExpiresAt: this.now() + tokens.expires_in * 1000,
      refreshToken,
      identifier,
    };
    await this.store.save(session);
    this.session = session;
    this.emit();
    return session;
  }

  async signIn(identifier: string, password: string): Promise<StoredSession> {
    const id = identifier.trim();
    const tokens = await this.identity.login({ identifier: id, password });
    return this.establish(tokens, id.toLowerCase());
  }

  async register(identifier: string, password: string, locale: Locale, idempotencyKey: string) {
    const id = identifier.trim();
    const tokens = await this.identity.register({ identifier: id, password, locale }, idempotencyKey);
    return this.establish(tokens, id.toLowerCase());
  }

  /** Rotates the refresh token. Concurrent callers share one network request. */
  refresh(): Promise<StoredSession> {
    if (this.refreshing) return this.refreshing;
    const current = this.session;
    if (!current) return Promise.reject(new ApiError({ status: 401, code: 'unauthorized' }));
    this.refreshing = (async () => {
      try {
        const tokens = await this.identity.refresh(current.refreshToken);
        return await this.establish(tokens, current.identifier, current.refreshToken);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          // Rotated elsewhere, revoked, or reuse detected: the session is gone.
          await this.clearLocal('expired');
        }
        throw e;
      } finally {
        this.refreshing = null;
      }
    })();
    return this.refreshing;
  }

  async accessToken(): Promise<string> {
    const s = this.session;
    if (!s) throw new ApiError({ status: 401, code: 'unauthorized' });
    if (s.accessExpiresAt - EXPIRY_SKEW_MS > this.now()) return s.accessToken;
    return (await this.refresh()).accessToken;
  }

  /** Runs an authenticated call; on 401 refreshes once and retries. */
  async withAuth<T>(call: (accessToken: string) => Promise<T>): Promise<T> {
    const token = await this.accessToken();
    try {
      return await call(token);
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 401) throw e;
      const fresh = await this.refresh();
      return call(fresh.accessToken);
    }
  }

  get claims() {
    return readClaims(this.session?.accessToken);
  }

  addSignOutHook(hook: (accessToken: string) => Promise<void>): () => void {
    this.signOutHooks.add(hook);
    return () => this.signOutHooks.delete(hook);
  }

  /**
   * Revokes the session server-side, then always clears it locally.
   * Returns false when the server could not be reached (the local session is cleared anyway and
   * the server-side session expires on its own; the UI tells the user).
   */
  async signOut(): Promise<boolean> {
    let revoked = true;
    if (this.session) {
      for (const hook of this.signOutHooks) {
        await this.withAuth(hook).catch(() => undefined);
      }
      try {
        await this.withAuth((t) => this.identity.logout(t));
      } catch (e) {
        revoked = e instanceof ApiError && e.status === 401; // already invalid server-side
      }
    }
    await this.clearLocal('signed_out');
    return revoked;
  }

  /**
   * Permanently deletes the account (identity: authDeleteAccount). No 401-refresh retry here: a
   * 401 means the password was wrong, and must not rotate the session. On success every session
   * is already revoked server-side, so only local state is wiped.
   */
  async deleteAccount(password: string): Promise<void> {
    const token = await this.accessToken();
    await this.identity.deleteAccount(token, password);
    await this.clearLocal('signed_out');
  }

  async clearLocal(reason: 'expired' | 'signed_out' = 'signed_out'): Promise<void> {
    await this.store.clear();
    this.session = null;
    this.emit(reason);
  }
}
