import { createContext, type ReactNode, useContext } from 'react';

import { type ApiClient, createApiClient } from './api/client';
import { deviceBiometrics } from './auth/biometrics';
import { SessionManager } from './auth/sessionManager';
import { TokenStore } from './auth/tokenStore';
import { PublicCache } from './cache/publicCache';
import { config } from './config';
import { createFileStore, type KeyValueStore } from './storage/fileStore';

export interface Services {
  api: ApiClient;
  tokenStore: TokenStore;
  session: SessionManager;
  prefs: KeyValueStore;
}

export function createServices(): Services {
  const api = createApiClient({
    identityBaseUrl: config.identityBaseUrl,
    providerBaseUrl: config.providerBaseUrl,
    fetch: (input, init) => fetch(input, init),
    cache: new PublicCache(createFileStore('cache', 'public-directory')),
  });
  const tokenStore = new TokenStore();
  return {
    api,
    tokenStore,
    session: new SessionManager(api.identity, tokenStore),
    prefs: createFileStore('document', 'prefs'),
  };
}

export const biometrics = deviceBiometrics;

const ServicesContext = createContext<Services | null>(null);

export function ServicesProvider({ services, children }: { services: Services; children: ReactNode }) {
  return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>;
}

export function useServices(): Services {
  const s = useContext(ServicesContext);
  if (!s) throw new Error('useServices must be used inside ServicesProvider');
  return s;
}

export const useApi = () => useServices().api;
