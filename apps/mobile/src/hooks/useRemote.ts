import { useCallback, useEffect, useRef, useState } from 'react';

import type { PublicResult } from '../api/client';
import { ApiError } from '../api/errors';
import type { MessageKey } from '../i18n';

export interface RemoteState<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  refreshing: boolean;
  fromCache: boolean;
  storedAt?: number;
  reload: () => void;
}

const toApiError = (e: unknown) =>
  e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown', detail: String(e) });

/** Loads a PublicResult (network first, cached public content as offline fallback). */
export function usePublic<T>(load: () => Promise<PublicResult<T>>, deps: readonly unknown[]): RemoteState<T> {
  return useLoader(async () => load(), deps);
}

/** Loads any promise (authenticated calls are never cached). */
export function useRemote<T>(load: () => Promise<T>, deps: readonly unknown[]): RemoteState<T> {
  return useLoader(async () => ({ data: await load(), fromCache: false }), deps);
}

function useLoader<T>(load: () => Promise<PublicResult<T>>, deps: readonly unknown[]): RemoteState<T> {
  const [state, setState] = useState<Omit<RemoteState<T>, 'reload'>>({
    data: undefined,
    error: undefined,
    loading: true,
    refreshing: false,
    fromCache: false,
  });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    let alive = true;
    // Data fetching: flag the request as in flight before the async load resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((s) => ({ ...s, loading: s.data === undefined, refreshing: s.data !== undefined, error: undefined }));
    loadRef
      .current()
      .then((r) => {
        if (alive) setState({ data: r.data, error: undefined, loading: false, refreshing: false, fromCache: r.fromCache, storedAt: r.storedAt });
      })
      .catch((e: unknown) => {
        if (alive) setState((s) => ({ ...s, error: toApiError(e), loading: false, refreshing: false }));
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { ...state, reload };
}

/** Maps an error to a user-facing message key. Never exposes raw server text for 5xx. */
export function errorKey(error: ApiError): MessageKey {
  switch (error.code) {
    case 'network_error':
      return 'error.network';
    case 'timeout':
      return 'error.timeout';
    case 'not_found':
      return 'error.notFound';
    case 'unauthorized':
      return 'error.unauthorized';
    case 'rate_limited':
      return 'error.rateLimited';
    case 'internal_error':
    case 'service_unavailable':
      return 'error.server';
    default:
      return 'error.generic';
  }
}
