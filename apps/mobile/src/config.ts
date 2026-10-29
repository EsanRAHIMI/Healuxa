import Constants from 'expo-constants';
import { Platform } from 'react-native';

export type AppEnv = 'development' | 'e2e' | 'staging' | 'production';

export interface AppConfig {
  appEnv: AppEnv;
  identityBaseUrl: string;
  providerBaseUrl: string;
  linkDomain: string;
  supportEmail: string;
  privacyPolicyUrl: string;
  features: { push: boolean };
  easProjectId?: string;
}

/**
 * The Android emulator reaches the host machine at 10.0.2.2, not localhost. Only applied to local
 * (development / e2e) builds; production URLs are always https and never rewritten.
 */
export function resolveHost(url: string, platform: string, appEnv: AppEnv): string {
  const local = appEnv === 'development' || appEnv === 'e2e';
  if (!local || platform !== 'android') return url;
  return url.replace('://localhost', '://10.0.2.2').replace('://127.0.0.1', '://10.0.2.2');
}

function load(): AppConfig {
  const extra = (Constants.expoConfig?.extra ?? {}) as Partial<AppConfig> & {
    eas?: { projectId?: string };
  };
  const appEnv = (extra.appEnv ?? 'development') as AppEnv;
  const identity = extra.identityBaseUrl ?? 'http://localhost:8201';
  const provider = extra.providerBaseUrl ?? 'http://localhost:8205';
  return {
    appEnv,
    identityBaseUrl: resolveHost(identity, Platform.OS, appEnv),
    providerBaseUrl: resolveHost(provider, Platform.OS, appEnv),
    linkDomain: extra.linkDomain ?? 'healuxa.ae',
    supportEmail: extra.supportEmail ?? 'privacy@healuxa.ae',
    privacyPolicyUrl: extra.privacyPolicyUrl ?? 'https://healuxa.ae/privacy',
    features: { push: Boolean(extra.features?.push) },
    easProjectId: extra.eas?.projectId,
  };
}

export const config: AppConfig = load();
