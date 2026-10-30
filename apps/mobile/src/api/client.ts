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
  Appointment,
  Branch,
  CaseCreate,
  CaseMessage,
  ConciergeCase,
  CustomerTransition,
  DeviceToken,
  InboxNotification,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  ProviderOption,
  SlotList,
  StatusTransition,
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
  /** identity: authDeleteAccount — permanent; requires the password again */
  deleteAccount(accessToken: string, password: string): Promise<void>;
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
  /** provider: getServiceOffering */
  getService(id: string): Promise<PublicResult<ServiceOffering>>;
}

/**
 * appointment-service. Slots are public (never cached: they change by the minute); every other
 * call is the signed-in customer's own data and goes through SessionManager.withAuth.
 */
export interface AppointmentsApi {
  /** appointment: listAvailableSlots (from/to = branch-local dates, max 31 days) */
  listSlots(serviceId: string, from: string, to: string): Promise<SlotList>;
  /** appointment: listAppointments (own appointments when no scope filter is sent) */
  list(token: string, q?: { cursor?: string; sort?: 'scheduled_at' | '-scheduled_at' }): Promise<Page<Appointment>>;
  /** appointment: getAppointment */
  get(token: string, id: string): Promise<Appointment>;
  /** appointment: createAppointment — places a short hold (status `held`) */
  hold(token: string, body: { service_id: string; scheduled_at: string }, idempotencyKey: string): Promise<Appointment>;
  /** appointment: transitionAppointment — customer transitions only (submit, cancel) */
  transition(token: string, id: string, transition: CustomerTransition, idempotencyKey: string, reasonCode?: 'customer_request'): Promise<Appointment>;
  /** appointment: rescheduleAppointment — returns the NEW linked appointment */
  reschedule(token: string, id: string, scheduledAt: string, idempotencyKey: string): Promise<Appointment>;
  /** appointment: listAppointmentTransitions */
  transitions(token: string, id: string): Promise<{ data: StatusTransition[] }>;
}

/** concierge-service: the customer's own cases, provider options and secure messages. */
export interface ConciergeApi {
  /** concierge: createConciergeCase */
  create(token: string, body: CaseCreate, idempotencyKey: string): Promise<ConciergeCase>;
  /** concierge: listMyConciergeCases */
  listMine(token: string, cursor?: string): Promise<Page<ConciergeCase>>;
  /** concierge: getConciergeCase */
  get(token: string, id: string): Promise<ConciergeCase>;
  /** concierge: transitionConciergeCase (customers may cancel) */
  cancel(token: string, id: string): Promise<ConciergeCase>;
  /** concierge: listConciergeCaseOptions */
  options(token: string, id: string): Promise<{ data: ProviderOption[] }>;
  /** concierge: selectConciergeCaseOption */
  selectOption(token: string, id: string, optionId: string): Promise<ProviderOption>;
  /** concierge: listConciergeCaseMessages (oldest first) */
  messages(token: string, id: string, cursor?: string): Promise<Page<CaseMessage>>;
  /** concierge: postConciergeCaseMessage */
  postMessage(token: string, id: string, body: string): Promise<CaseMessage>;
  /** concierge: markConciergeCaseMessagesRead */
  markRead(token: string, id: string): Promise<void>;
}

/** notification-service: in-app inbox, channel preferences and push device tokens. */
export interface NotificationsApi {
  /** notification: listNotifications */
  inbox(token: string, q?: { unread_only?: boolean; cursor?: string }): Promise<Page<InboxNotification>>;
  /** notification: getUnreadNotificationCount */
  unreadCount(token: string): Promise<{ unread: number }>;
  /** notification: markNotificationRead */
  markRead(token: string, id: string): Promise<InboxNotification>;
  /** notification: markAllNotificationsRead */
  markAllRead(token: string): Promise<{ marked: number }>;
  /** notification: getPreferences (own user id only) */
  preferences(token: string, userId: string): Promise<NotificationPreferences>;
  /** notification: updatePreferences (omitted fields keep their value) */
  updatePreferences(token: string, userId: string, body: NotificationPreferencesUpdate): Promise<NotificationPreferences>;
  /** notification: registerDeviceToken (re-registering the same token is idempotent server-side) */
  registerDevice(token: string, platform: 'ios' | 'android', deviceToken: string): Promise<DeviceToken>;
  /** notification: deleteDeviceToken */
  deleteDevice(token: string, id: string): Promise<void>;
}

export interface ApiClient {
  identity: IdentityApi;
  directory: DirectoryApi;
  appointments: AppointmentsApi;
  concierge: ConciergeApi;
  notifications: NotificationsApi;
}

export interface ApiClientOptions {
  identityBaseUrl: string;
  providerBaseUrl: string;
  appointmentBaseUrl?: string;
  conciergeBaseUrl?: string;
  notificationBaseUrl?: string;
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
    deleteAccount: async (accessToken, password) => {
      await request<void>(f, ID, '/v1/auth/delete-account', { method: 'POST', accessToken, body: { password } });
    },
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
    getService: (id) => publicGet(`/v1/services/${encodeURIComponent(id)}`),
  };

  const AP = opts.appointmentBaseUrl ?? PV;
  const CO = opts.conciergeBaseUrl ?? PV;
  const NO = opts.notificationBaseUrl ?? PV;
  const enc = encodeURIComponent;

  const appointments: AppointmentsApi = {
    listSlots: (serviceId, from, to) => request(f, AP, `/v1/services/${enc(serviceId)}/slots`, { query: { from, to } }),
    list: (accessToken, q) => request(f, AP, '/v1/appointments', { accessToken, query: { limit: 50, ...q } }),
    get: (accessToken, id) => request(f, AP, `/v1/appointments/${enc(id)}`, { accessToken }),
    hold: (accessToken, body, key) =>
      request(f, AP, '/v1/appointments', { method: 'POST', accessToken, body: { ...body, channel: 'app' }, headers: { 'Idempotency-Key': key } }),
    transition: (accessToken, id, transition, key, reason_code) =>
      request(f, AP, `/v1/appointments/${enc(id)}/status`, {
        method: 'POST',
        accessToken,
        body: reason_code ? { transition, reason_code } : { transition },
        headers: { 'Idempotency-Key': key },
      }),
    reschedule: (accessToken, id, scheduled_at, key) =>
      request(f, AP, `/v1/appointments/${enc(id)}/reschedule`, {
        method: 'POST',
        accessToken,
        body: { scheduled_at },
        headers: { 'Idempotency-Key': key },
      }),
    transitions: (accessToken, id) => request(f, AP, `/v1/appointments/${enc(id)}/transitions`, { accessToken }),
  };

  const concierge: ConciergeApi = {
    create: (accessToken, body, key) =>
      request(f, CO, '/v1/concierge/cases', { method: 'POST', accessToken, body, headers: { 'Idempotency-Key': key } }),
    listMine: (accessToken, cursor) => request(f, CO, '/v1/concierge/cases', { accessToken, query: { limit: 50, cursor } }),
    get: (accessToken, id) => request(f, CO, `/v1/concierge/cases/${enc(id)}`, { accessToken }),
    cancel: (accessToken, id) =>
      request(f, CO, `/v1/concierge/cases/${enc(id)}/transitions`, { method: 'POST', accessToken, body: { to_status: 'cancelled' } }),
    options: (accessToken, id) => request(f, CO, `/v1/concierge/cases/${enc(id)}/options`, { accessToken }),
    selectOption: (accessToken, id, optionId) =>
      request(f, CO, `/v1/concierge/cases/${enc(id)}/options/${enc(optionId)}/select`, { method: 'POST', accessToken }),
    messages: (accessToken, id, cursor) =>
      request(f, CO, `/v1/concierge/cases/${enc(id)}/messages`, { accessToken, query: { limit: 100, cursor } }),
    postMessage: (accessToken, id, body) =>
      request(f, CO, `/v1/concierge/cases/${enc(id)}/messages`, { method: 'POST', accessToken, body: { body } }),
    markRead: async (accessToken, id) => {
      await request<unknown>(f, CO, `/v1/concierge/cases/${enc(id)}/messages/read`, { method: 'POST', accessToken, body: {} });
    },
  };

  const notifications: NotificationsApi = {
    inbox: (accessToken, q) => request(f, NO, '/v1/notifications', { accessToken, query: { limit: 50, ...q } }),
    unreadCount: (accessToken) => request(f, NO, '/v1/notifications/unread-count', { accessToken }),
    markRead: (accessToken, id) => request(f, NO, `/v1/notifications/${enc(id)}/read`, { method: 'POST', accessToken }),
    markAllRead: (accessToken) => request(f, NO, '/v1/notifications/read-all', { method: 'POST', accessToken }),
    preferences: (accessToken, userId) => request(f, NO, `/v1/notifications/preferences/${enc(userId)}`, { accessToken }),
    updatePreferences: (accessToken, userId, body) =>
      request(f, NO, `/v1/notifications/preferences/${enc(userId)}`, { method: 'PUT', accessToken, body }),
    registerDevice: (accessToken, platform, token) =>
      request(f, NO, '/v1/notification-devices', { method: 'POST', accessToken, body: { platform, token } }),
    deleteDevice: async (accessToken, id) => {
      await request<void>(f, NO, `/v1/notification-devices/${enc(id)}`, { method: 'DELETE', accessToken });
    },
  };

  return { identity, directory, appointments, concierge, notifications };
}
