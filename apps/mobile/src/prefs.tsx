import { createContext, type ReactNode, useContext, useMemo, useState } from 'react';

import type { Language } from './i18n';
import type { KeyValueStore } from './storage/fileStore';

/** Non-sensitive UI preferences (stored as a plain file — never tokens or personal data). */
export interface Prefs {
  language?: Language;
  welcomeSeen?: boolean;
}

export async function loadPrefs(store: KeyValueStore): Promise<Prefs> {
  try {
    const raw = await store.get('prefs');
    return raw ? (JSON.parse(raw) as Prefs) : {};
  } catch {
    return {};
  }
}

export async function savePrefs(store: KeyValueStore, prefs: Prefs): Promise<void> {
  await store.set('prefs', JSON.stringify(prefs));
}

interface PrefsValue {
  prefs: Prefs;
  update(patch: Partial<Prefs>): Promise<void>;
}

const PrefsContext = createContext<PrefsValue | null>(null);

export function PrefsProvider({ initial, store, children }: { initial: Prefs; store: KeyValueStore; children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(initial);
  const value = useMemo<PrefsValue>(
    () => ({
      prefs,
      update: async (patch) => {
        const next = { ...prefs, ...patch };
        setPrefs(next);
        await savePrefs(store, next).catch(() => undefined);
      },
    }),
    [prefs, store]
  );
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): PrefsValue {
  const v = useContext(PrefsContext);
  if (!v) throw new Error('usePrefs must be used inside PrefsProvider');
  return v;
}
