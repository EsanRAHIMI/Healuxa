/**
 * RFC 9457 problem details -> typed errors.
 *
 * Healuxa services answer non-2xx with the shared `Error` schema
 * (packages/api-contracts/openapi/_shared/components.yaml). Two framework shapes also occur in practice
 * and are normalised here: FastAPI `HTTPException(detail=<problem>)` -> `{ "detail": { ...problem } }`, and
 * request-validation failures -> `{ "detail": [{ loc, msg, type }] }`.
 */

export type ErrorCode =
  | "validation_error"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "idempotency_conflict"
  | "rate_limited"
  | "unprocessable"
  | "internal_error"
  | "service_unavailable"
  | "network_error";

export interface FieldError {
  field: string;
  code: string;
  message?: string;
}

export interface ProblemDetails {
  type?: string;
  title: string;
  status: number;
  code: ErrorCode;
  detail?: string;
  instance?: string;
  trace_id?: string;
  errors?: FieldError[];
}

const KNOWN_CODES = new Set<ErrorCode>([
  "validation_error",
  "unauthorized",
  "forbidden",
  "not_found",
  "conflict",
  "idempotency_conflict",
  "rate_limited",
  "unprocessable",
  "internal_error",
  "service_unavailable",
]);

const CODE_BY_STATUS: Record<number, ErrorCode> = {
  400: "validation_error",
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  409: "conflict",
  422: "unprocessable",
  429: "rate_limited",
  503: "service_unavailable",
};

const TITLE_BY_CODE: Record<ErrorCode, string> = {
  validation_error: "Validation failed",
  unauthorized: "Unauthorized",
  forbidden: "Forbidden",
  not_found: "Not found",
  conflict: "Conflict",
  idempotency_conflict: "Idempotency conflict",
  rate_limited: "Too many requests",
  unprocessable: "Unprocessable",
  internal_error: "Internal error",
  service_unavailable: "Service unavailable",
  network_error: "Network error",
};

export class HealuxaApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly title: string;
  readonly detail: string | undefined;
  readonly type: string | undefined;
  readonly instance: string | undefined;
  readonly traceId: string | undefined;
  readonly fieldErrors: FieldError[];
  /** Seconds, from `Retry-After`, when the server sent one. */
  readonly retryAfter: number | undefined;

  constructor(problem: ProblemDetails, options: { retryAfter?: number; cause?: unknown } = {}) {
    super(problem.detail ?? problem.title, { cause: options.cause });
    this.name = new.target.name;
    this.status = problem.status;
    this.code = problem.code;
    this.title = problem.title;
    this.detail = problem.detail;
    this.type = problem.type;
    this.instance = problem.instance;
    this.traceId = problem.trace_id;
    this.fieldErrors = problem.errors ?? [];
    this.retryAfter = options.retryAfter;
  }

  /** Field-level message for a form input, if the server reported one. */
  fieldMessage(field: string): string | undefined {
    const hit = this.fieldErrors.find((e) => e.field === field || e.field.endsWith(`.${field}`));
    return hit ? (hit.message ?? hit.code) : undefined;
  }

  toJSON(): ProblemDetails {
    return {
      type: this.type,
      title: this.title,
      status: this.status,
      code: this.code,
      detail: this.detail,
      instance: this.instance,
      trace_id: this.traceId,
      errors: this.fieldErrors,
    };
  }
}

export class ValidationError extends HealuxaApiError {}
export class UnauthorizedError extends HealuxaApiError {}
export class ForbiddenError extends HealuxaApiError {}
export class NotFoundError extends HealuxaApiError {}
export class ConflictError extends HealuxaApiError {}
export class IdempotencyConflictError extends ConflictError {}
export class UnprocessableError extends HealuxaApiError {}
export class RateLimitedError extends HealuxaApiError {}
export class ServiceUnavailableError extends HealuxaApiError {}
export class InternalServerError extends HealuxaApiError {}
/** The request never produced an HTTP response (DNS, connection refused, timeout, CORS, offline). */
export class NetworkError extends HealuxaApiError {}

const CLASS_BY_CODE: Record<ErrorCode, new (p: ProblemDetails, o?: { retryAfter?: number; cause?: unknown }) => HealuxaApiError> = {
  validation_error: ValidationError,
  unauthorized: UnauthorizedError,
  forbidden: ForbiddenError,
  not_found: NotFoundError,
  conflict: ConflictError,
  idempotency_conflict: IdempotencyConflictError,
  rate_limited: RateLimitedError,
  unprocessable: UnprocessableError,
  internal_error: InternalServerError,
  service_unavailable: ServiceUnavailableError,
  network_error: NetworkError,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asProblem(value: unknown): Partial<ProblemDetails> | null {
  if (!isRecord(value)) return null;
  if (typeof value.code === "string" || typeof value.title === "string") return value as Partial<ProblemDetails>;
  return null;
}

/** FastAPI request-validation entries: { loc: ["body", "name"], msg, type }. */
function fromValidationList(list: unknown[]): FieldError[] {
  return list.filter(isRecord).map((entry) => {
    const loc = Array.isArray(entry.loc) ? entry.loc.filter((p) => p !== "body" && p !== "query" && p !== "path") : [];
    return {
      field: loc.length ? loc.join(".") : "request",
      code: typeof entry.type === "string" ? entry.type : "invalid",
      message: typeof entry.msg === "string" ? entry.msg : undefined,
    };
  });
}

/** Normalise any error body + status into ProblemDetails. Never throws. */
export function normalizeProblem(status: number, body: unknown, traceHeader?: string | null): ProblemDetails {
  let problem: Partial<ProblemDetails> | null = asProblem(body);
  let fieldErrors: FieldError[] | undefined;

  if (isRecord(body) && "detail" in body) {
    const detail = body.detail;
    const nested = asProblem(detail);
    if (nested) problem = nested;
    else if (Array.isArray(detail)) {
      fieldErrors = fromValidationList(detail);
      problem = { code: "validation_error", title: TITLE_BY_CODE.validation_error, detail: fieldErrors[0]?.message };
    } else if (typeof detail === "string" && !problem?.code) {
      problem = { detail };
    }
  }

  const rawCode = problem?.code;
  const code: ErrorCode =
    rawCode && KNOWN_CODES.has(rawCode as ErrorCode)
      ? (rawCode as ErrorCode)
      : (CODE_BY_STATUS[status] ?? (status >= 500 ? "internal_error" : "validation_error"));

  return {
    type: problem?.type,
    title: problem?.title ?? TITLE_BY_CODE[code],
    status: typeof problem?.status === "number" ? problem.status : status,
    code,
    detail: problem?.detail,
    instance: problem?.instance,
    trace_id: problem?.trace_id ?? traceHeader ?? undefined,
    errors: problem?.errors ?? fieldErrors,
  };
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return seconds;
  const date = Date.parse(value);
  return Number.isNaN(date) ? undefined : Math.max(0, Math.round((date - Date.now()) / 1000));
}

export function toApiError(status: number, body: unknown, headers?: Headers): HealuxaApiError {
  const problem = normalizeProblem(status, body, headers?.get("x-trace-id"));
  const Klass = CLASS_BY_CODE[problem.code];
  return new Klass(problem, { retryAfter: parseRetryAfter(headers?.get("retry-after") ?? null) });
}

export function networkError(cause: unknown): NetworkError {
  return new NetworkError(
    {
      title: TITLE_BY_CODE.network_error,
      status: 0,
      code: "network_error",
      detail: cause instanceof Error ? cause.message : "The service could not be reached",
    },
    { cause },
  );
}

export function isApiError(error: unknown, code?: ErrorCode | ErrorCode[]): error is HealuxaApiError {
  if (!(error instanceof HealuxaApiError)) return false;
  if (code === undefined) return true;
  return Array.isArray(code) ? code.includes(error.code) : error.code === code;
}
