/**
 * Normalised error model for every backend call. Services answer RFC 9457 problem details
 * (`_shared/components.yaml#/components/schemas/Error`); FastAPI wraps some of them as
 * `{ "detail": { ...problem } }` and request validation as `{ "detail": [ ... ] }`.
 */
export type ApiErrorCode =
  | 'validation_error'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'idempotency_conflict'
  | 'rate_limited'
  | 'unprocessable'
  | 'internal_error'
  | 'service_unavailable'
  | 'network_error'
  | 'timeout'
  | 'unknown';

export interface FieldError {
  field: string;
  code: string;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly detail?: string;
  readonly traceId?: string;
  readonly fieldErrors: FieldError[];

  constructor(init: {
    status: number;
    code: ApiErrorCode;
    title?: string;
    detail?: string;
    traceId?: string;
    fieldErrors?: FieldError[];
  }) {
    super(init.title ?? init.detail ?? init.code);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.detail = init.detail;
    this.traceId = init.traceId;
    this.fieldErrors = init.fieldErrors ?? [];
  }

  get isNetwork(): boolean {
    return this.code === 'network_error' || this.code === 'timeout';
  }
}

const KNOWN: ReadonlySet<string> = new Set([
  'validation_error',
  'unauthorized',
  'forbidden',
  'not_found',
  'conflict',
  'idempotency_conflict',
  'rate_limited',
  'unprocessable',
  'internal_error',
  'service_unavailable',
]);

function codeForStatus(status: number): ApiErrorCode {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 409) return 'conflict';
  if (status === 422) return 'validation_error';
  if (status === 429) return 'rate_limited';
  if (status === 503) return 'service_unavailable';
  if (status >= 500) return 'internal_error';
  return 'unknown';
}

type Json = Record<string, unknown>;
const isObject = (v: unknown): v is Json => typeof v === 'object' && v !== null && !Array.isArray(v);

export function parseErrorBody(status: number, body: unknown): ApiError {
  let problem: Json | undefined;
  let fieldErrors: FieldError[] = [];
  if (isObject(body)) {
    if (typeof body.code === 'string') problem = body;
    else if (isObject(body.detail)) problem = body.detail;
    else if (Array.isArray(body.detail)) {
      // FastAPI request validation: [{ loc: [...], msg, type }]
      fieldErrors = body.detail.filter(isObject).map((item) => ({
        field: Array.isArray(item.loc) ? item.loc.filter((p) => p !== 'body').join('.') : 'request',
        code: typeof item.type === 'string' ? item.type : 'invalid',
        message: typeof item.msg === 'string' ? item.msg : undefined,
      }));
    }
  }
  if (problem && Array.isArray(problem.errors)) {
    fieldErrors = problem.errors.filter(isObject).map((e) => ({
      field: String(e.field ?? ''),
      code: String(e.code ?? 'invalid'),
      message: typeof e.message === 'string' ? e.message : undefined,
    }));
  }
  const rawCode = typeof problem?.code === 'string' ? problem.code : undefined;
  return new ApiError({
    status,
    code: rawCode && KNOWN.has(rawCode) ? (rawCode as ApiErrorCode) : codeForStatus(status),
    title: typeof problem?.title === 'string' ? problem.title : undefined,
    detail: typeof problem?.detail === 'string' ? problem.detail : undefined,
    traceId: typeof problem?.trace_id === 'string' ? problem.trace_id : undefined,
    fieldErrors,
  });
}
