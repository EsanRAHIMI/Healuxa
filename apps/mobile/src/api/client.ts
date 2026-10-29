/**
 * The app's API adapter. Screens depend on this interface only, so the transport and wire types
 * can be replaced by the shared `@healuxa/api-client` package without touching UI code.
 *
 * Operation ids refer to packages/api-contracts/openapi/*.yaml.
 */
import type { PublicCache } from '../cache/publicCache';
import { ApiError } from './errors';
import { buildUrl, type FetchLike, type Query, request } from './http';
import type {
  Branch,
  Facility,
  LoginRequest,
  OperatingHours,
  Page,
  Provider,
  ProviderSearch,
  RegisterRequest,
  ServiceOffering,
  ServiceSearch,
  Session,
  TokenResponse,
} from './types';

export interface PublicResult<T> {
  data: T;
  /** true when the network failed and cached public content is shown instead */
  fromCache: boolean;
  storedAt?: number;
}

export interface IdentityApi {
  /** identity: authRegister */
  register(body: RegisterRequest, idempotencyKey: string): Promise<TokenResponse>;
  /** identity: authLogin */
  login(body: LoginRequest): Promise<TokenResponse>;
  /** identity: authRefresh (rotates the refresh token) */
  refresh(refreshToken: string): Promise<TokenResponse>;
  /** identity: authLogout */
  logout(accessToken: string): Promise<void>;
  /** identity: listSessions */
  listSessions(accessToken: string, cursor?: string): Promise<Page<Session>>;
  /** identity: revokeSession */
  revokeSession(accessToken: string, sessionId: string): Promise<void>;
}

export interface DirectoryApi {
  /** provider: searchProviders */
  searchProviders(q: ProviderSearch): Promise<PublicResult<Page<Provider>>>;
  /** provider: getProvider */
  getProvider(id: string): Promise<PublicResult<Provider>>;
  /** provider: searchFacilities */
  searchFacilities(q: { city?: string; limit?: number; cursor?: string }): Promise<PublicResult<Page<Facility>>>;
  /** provider: getFacility */
  getFacility(id: string): Promise<PublicResult<Facility>>;
  /** provider: listBranches */
  listBranches(facilityId: string): Promise<PublicResult<{ data: Branch[] }>>;
  /** provider: getOperatingHours */
  getOperatingHours(branchId: string): Promise<PublicResult<OperatingHours>>;
  /** provider: listServices */
  listServices(q: ServiceSearch): Promise<PublicResult<Page<ServiceOffering>>>;
}

export interface ApiClient {
  identity: IdentityApi;
  directory: DirectoryApi;
}

export interface ApiClientOptions {
  identityBaseUrl: string;
  providerBaseUrl: string;
  fetch: FetchLike;
  cache?: PublicCache;
}

export function createApiClient(opts: ApiClientOptions): ApiClient {
  const { identityBaseUrl: ID, providerBaseUrl: PV, cache } = opts;
  const f = opts.fetch;

  async function publicGet<T>(path: string, query?: Query): Promise<PublicResult<T>> {
    const key = buildUrl('', path, query);
    try {
      const data = await request<T>(f, PV, path, { query });
      if (cache) await cache.put(key, data).catch(() => undefined);
      return { data, fromCache: false };
    } catch (e) {
      if (cache && e instanceof ApiError && e.isNetwork) {
        const hit = await cache.get<T>(key);
        if (hit) return { data: hit.value, fromCache: true, storedAt: hit.storedAt };
      }
      throw e;
    }
  }

  const identity: IdentityApi = {
    register: (body, idempotencyKey) =>
      request<TokenResponse>(f, ID, '/v1/auth/register', {
        method: 'POST',
        body,
        headers: { 'Idempotency-Key': idempotencyKey },
      }),
    login: (body) => request<TokenResponse>(f, ID, '/v1/auth/login', { method: 'POST', body }),
    refresh: (refreshToken) =>
      request<TokenResponse>(f, ID, '/v1/auth/refresh', {
        method: 'POST',
        body: { refresh_token: refreshToken },
      }),
    logout: async (accessToken) => {
      await request<void>(f, ID, '/v1/auth/logout', { method: 'POST', accessToken });
    },
    listSessions: (accessToken, cursor) =>
      request<Page<Session>>(f, ID, '/v1/sessions', { accessToken, query: { limit: 50, cursor } }),
    revokeSession: async (accessToken, sessionId) => {
      await request<void>(f, ID, `/v1/sessions/${encodeURIComponent(sessionId)}`, {
        method: 'DELETE',
        accessToken,
      });
    },
  };

  const directory: DirectoryApi = {
    searchProviders: (q) => publicGet('/v1/providers', { ...q }),
    getProvider: (id) => publicGet(`/v1/providers/${encodeURIComponent(id)}`),
    searchFacilities: (q) => publicGet('/v1/facilities', { ...q }),
    getFacility: (id) => publicGet(`/v1/facilities/${encodeURIComponent(id)}`),
    listBranches: (facilityId) => publicGet(`/v1/facilities/${encodeURIComponent(facilityId)}/branches`),
    getOperatingHours: (branchId) => publicGet(`/v1/branches/${encodeURIComponent(branchId)}/operating-hours`),
    listServices: (q) => publicGet('/v1/services', { ...q }),
  };

  return { identity, directory };
}
