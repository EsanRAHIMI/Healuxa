/**
 * Local i18n adapter (en / ar / fa with RTL). Kept behind `useI18n()` so it can be swapped for the
 * shared `@healuxa/i18n` package once that lands on main.
 */
import { reloadAppAsync } from 'expo';
import { getLocales } from 'expo-localization';
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { I18nManager } from 'react-native';

import { ar } from './ar';
import { en, type MessageKey, type Messages } from './en';
import { fa } from './fa';

export type Language = 'en' | 'ar' | 'fa';
export const LANGUAGES: readonly { code: Language; nativeName: string }[] = [
  { code: 'en', nativeName: 'English' },
  { code: 'ar', nativeName: 'العربية' },
  { code: 'fa', nativeName: 'فارسی' },
];

const CATALOG: Record<Language, Messages> = { en, ar, fa };
const RTL: ReadonlySet<Language> = new Set(['ar', 'fa']);

export const isRTLLanguage = (lang: Language) => RTL.has(lang);

export function isLanguage(v: unknown): v is Language {
  return v === 'en' || v === 'ar' || v === 'fa';
}

export function translate(lang: Language, key: MessageKey, params?: Record<string, string | number>): string {
  const template = CATALOG[lang][key] ?? en[key] ?? key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (m, name: string) => (name in params ? String(params[name]) : m));
}

export function deviceLanguage(): Language {
  const code = getLocales()[0]?.languageCode ?? 'en';
  return isLanguage(code) ? code : 'en';
}

/**
 * Aligns the native layout direction with the language. Returns true when the change only takes
 * effect after a reload (React Native applies I18nManager direction at startup).
 */
export function applyDirection(lang: Language, manager: Pick<typeof I18nManager, 'allowRTL' | 'forceRTL' | 'isRTL'> = I18nManager): boolean {
  const rtl = isRTLLanguage(lang);
  manager.allowRTL(rtl);
  if (manager.isRTL !== rtl) {
    manager.forceRTL(rtl);
    return true;
  }
  return false;
}

export interface I18nValue {
  language: Language;
  isRTL: boolean;
  /** layout direction will flip after restart */
  restartRequired: boolean;
  t: (key: MessageKey, params?: Record<string, string | number>) => string;
  setLanguage: (lang: Language) => Promise<void>;
  restart: () => Promise<void>;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  initialLanguage,
  onPersist,
  children,
}: {
  initialLanguage: Language;
  onPersist?: (lang: Language) => Promise<void>;
  children: ReactNode;
}) {
  const [language, setLang] = useState<Language>(initialLanguage);
  const [restartRequired, setRestartRequired] = useState(false);

  const setLanguage = useCallback(
    async (lang: Language) => {
      setLang(lang);
      setRestartRequired(applyDirection(lang));
      await onPersist?.(lang);
    },
    [onPersist]
  );

  const value = useMemo<I18nValue>(
    () => ({
      language,
      isRTL: isRTLLanguage(language),
      restartRequired,
      t: (key, params) => translate(language, key, params),
      setLanguage,
      restart: () => reloadAppAsync('language direction changed'),
    }),
    [language, restartRequired, setLanguage]
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const v = useContext(I18nContext);
  if (!v) throw new Error('useI18n must be used inside I18nProvider');
  return v;
}

export type { MessageKey };
