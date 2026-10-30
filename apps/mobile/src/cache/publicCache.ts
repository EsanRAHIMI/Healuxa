import type { KeyValueStore } from '../storage/fileStore';

/**
 * Offline-safe cache for PUBLIC directory content only (provider directory, provider profiles,
 * facilities, branches, opening hours, service catalog). Anything else — and every request made
 * with an access token — is rejected so health or account data can never be persisted here.
 */
const PUBLIC_PATHS: readonly RegExp[] = [
  /^\/v1\/providers(\?.*)?$/,
  /^\/v1\/providers\/[A-Za-z0-9]+$/,
  /^\/v1\/facilities(\?.*)?$/,
  /^\/v1\/facilities\/[A-Za-z0-9]+$/,
  /^\/v1\/facilities\/[A-Za-z0-9]+\/branches$/,
  /^\/v1\/branches\/[A-Za-z0-9]+\/operating-hours$/,
  /^\/v1\/services(\?.*)?$/,
  /^\/v1\/services\/[A-Za-z0-9]+$/,
];

export function isCacheablePublicPath(pathWithQuery: string, authenticated: boolean): boolean {
  if (authenticated) return false;
  if (pathWithQuery.startsWith('/v1/providers/me')) return false;
  return PUBLIC_PATHS.some((re) => re.test(pathWithQuery));
}

interface Entry<T> {
  storedAt: number;
  value: T;
}

export interface CachedResult<T> {
  value: T;
  stale: boolean;
  storedAt: number;
}

export class PublicCache {
  constructor(
    private readonly store: KeyValueStore,
    private readonly maxAgeMs = 24 * 60 * 60 * 1000,
    private readonly now: () => number = Date.now
  ) {}

  async put<T>(pathWithQuery: string, value: T, authenticated = false): Promise<void> {
    if (!isCacheablePublicPath(pathWithQuery, authenticated)) {
      throw new Error(`Refusing to cache non-public path: ${pathWithQuery}`);
    }
    const entry: Entry<T> = { storedAt: this.now(), value };
    await this.store.set(pathWithQuery, JSON.stringify(entry));
  }

  /** Returns cached content (even if stale, flagged) or null. Entries older than 7 days are dropped. */
  async get<T>(pathWithQuery: string): Promise<CachedResult<T> | null> {
    if (!isCacheablePublicPath(pathWithQuery, false)) return null;
    const raw = await this.store.get(pathWithQuery);
    if (!raw) return null;
    try {
      const entry = JSON.parse(raw) as Entry<T>;
      const age = this.now() - entry.storedAt;
      if (age > 7 * 24 * 60 * 60 * 1000) {
        await this.store.remove(pathWithQuery);
        return null;
      }
      return { value: entry.value, stale: age > this.maxAgeMs, storedAt: entry.storedAt };
    } catch {
      await this.store.remove(pathWithQuery);
      return null;
    }
  }

  clear(): Promise<void> {
    return this.store.clear();
  }
}
