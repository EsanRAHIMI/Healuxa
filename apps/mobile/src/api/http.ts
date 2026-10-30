import { ApiError, parseErrorBody } from './errors';

export type Query = Record<string, string | number | boolean | undefined | null>;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  query?: Query;
  body?: unknown;
  headers?: Record<string, string>;
  accessToken?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export function buildUrl(base: string, path: string, query?: Query): string {
  const qs = Object.entries(query ?? {})
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return `${base}${path}${qs ? `?${qs}` : ''}`;
}

/** Thin JSON-over-HTTP transport. Throws ApiError for every non-2xx and for network failures. */
export async function request<T>(
  fetchImpl: FetchLike,
  base: string,
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 15000);
  const onAbort = () => controller.abort();
  options.signal?.addEventListener('abort', onAbort);
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.accessToken) headers.Authorization = `Bearer ${options.accessToken}`;

  let response: Response;
  try {
    response = await fetchImpl(buildUrl(base, path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = controller.signal.aborted && !options.signal?.aborted;
    throw new ApiError({
      status: 0,
      code: aborted ? 'timeout' : 'network_error',
      detail: e instanceof Error ? e.message : String(e),
    });
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', onAbort);
  }

  const text = await response.text();
  let json: unknown = undefined;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = undefined;
    }
  }
  if (!response.ok) throw parseErrorBody(response.status, json);
  return json as T;
}
