import { Directory, File, Paths } from 'expo-file-system';

/**
 * Small async key/value store backed by plain files. Used ONLY for non-sensitive data:
 * the public directory cache (cache dir) and UI preferences (document dir).
 * Tokens and anything identifying go to ../auth/tokenStore.ts (Keychain / Keystore).
 */
export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
  clear(): Promise<void>;
}

const safeName = (key: string) => key.replace(/[^a-zA-Z0-9._-]/g, '_');

export function createFileStore(kind: 'cache' | 'document', namespace: string): KeyValueStore {
  const dir = () => new Directory(kind === 'cache' ? Paths.cache : Paths.document, namespace);
  const ensureDir = () => {
    const d = dir();
    if (!d.exists) d.create({ intermediates: true, idempotent: true });
    return d;
  };
  return {
    async get(key) {
      try {
        const f = new File(dir(), `${safeName(key)}.json`);
        return f.exists ? await f.text() : null;
      } catch {
        return null;
      }
    },
    async set(key, value) {
      const f = new File(ensureDir(), `${safeName(key)}.json`);
      f.write(value);
    },
    async remove(key) {
      const f = new File(dir(), `${safeName(key)}.json`);
      if (f.exists) f.delete();
    },
    async clear() {
      const d = dir();
      if (d.exists) d.delete();
    },
  };
}

/** In-memory implementation used by tests and as a fallback. */
export function createMemoryStore(): KeyValueStore & { dump(): Record<string, string> } {
  const map = new Map<string, string>();
  return {
    async get(key) {
      return map.get(key) ?? null;
    },
    async set(key, value) {
      map.set(key, value);
    },
    async remove(key) {
      map.delete(key);
    },
    async clear() {
      map.clear();
    },
    dump: () => Object.fromEntries(map),
  };
}
