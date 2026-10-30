import createClient, { type Client } from "openapi-fetch";

import { HealuxaApiError, networkError, toApiError } from "./errors";
import type { paths as AppointmentPaths } from "./generated/appointment";
import type { paths as AssessmentPaths } from "./generated/assessment";
import type { paths as ConciergePaths } from "./generated/concierge";
import type { paths as IdentityPaths } from "./generated/identity";
import type { paths as NotificationPaths } from "./generated/notification";
import type { paths as PaymentPaths } from "./generated/payment";
import type { paths as ProfilePaths } from "./generated/profile";
import type { paths as ProviderPaths } from "./generated/provider";
import type { paths as SubscriptionPaths } from "./generated/subscription";

/** One entry per backend service; each gets its own base URL (they share path prefixes like /services). */
export type ServiceName =
  | "identity"
  | "provider"
  | "profile"
  | "assessment"
  | "appointment"
  | "concierge"
  | "notification"
  | "payment"
  | "subscription";

export interface ServicePaths {
  identity: IdentityPaths;
  provider: ProviderPaths;
  profile: ProfilePaths;
  assessment: AssessmentPaths;
  appointment: AppointmentPaths;
  concierge: ConciergePaths;
  notification: NotificationPaths;
  payment: PaymentPaths;
  subscription: SubscriptionPaths;
}

export type ServiceClient<S extends ServiceName> = Client<ServicePaths[S], "application/json">;

/** openapi-fetch hands custom fetch a Request plus the optional `requestInitExt` object. */
export type FetchLike = (input: Request, init?: Record<string, unknown>) => Promise<Response>;

export interface TokenProvider {
  /** Current access token (may be read from secure storage, a cookie jar, memory…). */
  getAccessToken(): string | null | undefined | Promise<string | null | undefined>;
  /**
   * Refresh-token rotation hook. Invoked when an authenticated request returns 401; concurrent 401s
   * share a single call (identity-service revokes every session on refresh-token reuse, so never call
   * the refresh endpoint twice with the same token). Return the new access token, or null when the
   * session cannot be renewed.
   */
  refresh?(): Promise<string | null>;
  /** Called when a 401 persists after refresh (or no refresh is possible). */
  onSessionExpired?(): void;
}

export interface HealuxaClientOptions {
  /** Base URL per service including the `/v1` prefix, e.g. `https://api.healuxa.com/v1`. */
  baseUrls: Partial<Record<ServiceName, string>>;
  auth?: TokenProvider;
  /** Defaults to globalThis.fetch (browser, Node 18+, React Native). */
  fetch?: FetchLike;
  /** Extra headers on every request (e.g. Accept-Language; on a server: X-Forwarded-For). */
  headers?: Record<string, string> | (() => Record<string, string>);
  /** Passed as fetch's 2nd argument, e.g. Next.js `{ next: { revalidate: 60 } }`. */
  requestInitExt?: Record<string, unknown>;
  /** Abort requests that take longer than this. */
  timeoutMs?: number;
}

export type HealuxaClient = { readonly [S in ServiceName]: ServiceClient<S> };

/** Collapse concurrent invocations into one in-flight promise. */
export function singleFlight<T>(fn: () => Promise<T>): () => Promise<T> {
  let inflight: Promise<T> | null = null;
  return () => {
    if (!inflight) {
      inflight = fn().finally(() => {
        inflight = null;
      });
    }
    return inflight;
  };
}

function withTimeout(request: Request, timeoutMs: number | undefined): Request {
  if (!timeoutMs || typeof AbortSignal === "undefined" || typeof AbortSignal.timeout !== "function") return request;
  const timeout = AbortSignal.timeout(timeoutMs);
  const signal = typeof AbortSignal.any === "function" ? AbortSignal.any([request.signal, timeout]) : timeout;
  return new Request(request, { signal });
}

export function createHealuxaClient(options: HealuxaClientOptions): HealuxaClient {
  const baseFetch: FetchLike = options.fetch ?? ((input, init) => globalThis.fetch(input, init as RequestInit));
  const auth = options.auth;
  const refresh = auth?.refresh ? singleFlight(() => auth.refresh!()) : null;

  const authedFetch: FetchLike = async (input, init) => {
    const extra = typeof options.headers === "function" ? options.headers() : (options.headers ?? {});
    for (const [name, value] of Object.entries(extra)) {
      if (!input.headers.has(name)) input.headers.set(name, value);
    }
    // Keep a pristine copy for a single retry after refresh (the body stream can only be read once).
    const retry = refresh ? input.clone() : null;
    const token = input.headers.has("Authorization") ? null : await auth?.getAccessToken();
    if (token) input.headers.set("Authorization", `Bearer ${token}`);

    const response = await baseFetch(withTimeout(input, options.timeoutMs), init);
    if (response.status !== 401 || !token || !auth) return response;

    const renewed = refresh ? await refresh().catch(() => null) : null;
    if (!renewed || !retry) {
      auth.onSessionExpired?.();
      return response;
    }
    retry.headers.set("Authorization", `Bearer ${renewed}`);
    const second = await baseFetch(withTimeout(retry, options.timeoutMs), init);
    if (second.status === 401) auth.onSessionExpired?.();
    return second;
  };

  const cache = new Map<ServiceName, ServiceClient<ServiceName>>();
  const make = <S extends ServiceName>(name: S): ServiceClient<S> => {
    const hit = cache.get(name);
    if (hit) return hit as unknown as ServiceClient<S>;
    const baseUrl = options.baseUrls[name];
    if (!baseUrl) throw new Error(`@healuxa/api-client: no base URL configured for "${name}"`);
    const client = createClient<ServicePaths[S]>({
      baseUrl: baseUrl.replace(/\/+$/, ""),
      fetch: authedFetch as (input: Request) => Promise<Response>,
      requestInitExt: options.requestInitExt,
      headers: { Accept: "application/json" },
    });
    cache.set(name, client as unknown as ServiceClient<ServiceName>);
    return client;
  };

  const names: ServiceName[] = ["identity", "provider", "profile", "assessment", "appointment", "concierge", "notification", "payment", "subscription"];
  const out = {} as Record<ServiceName, unknown>;
  for (const name of names) Object.defineProperty(out, name, { enumerable: true, get: () => make(name) });
  return out as HealuxaClient;
}

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

export interface Unwrapped<T> {
  data: T;
  response: Response;
  /** ETag header (weak/strong), for If-Match on the next update. */
  etag: string | null;
}

/** Await an openapi-fetch call; return the response data or throw a typed HealuxaApiError. */
export async function unwrapResponse<T>(call: Promise<FetchResult<T>>): Promise<Unwrapped<T>> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch (error) {
    if (error instanceof HealuxaApiError) throw error;
    throw networkError(error);
  }
  const { response } = result;
  if (!response.ok) throw toApiError(response.status, result.error, response.headers);
  return { data: result.data as T, response, etag: response.headers.get("etag") };
}

export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  return (await unwrapResponse(call)).data;
}
