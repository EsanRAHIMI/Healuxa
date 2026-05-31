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
  | "service_unavailable";

export interface FieldError {
  field: string;
  code: string;
  message?: string;
}

/** RFC 9457-compatible error per packages/api-contracts/openapi/_shared/components.yaml */
export interface ApiErrorBody {
  type?: string;
  title: string;
  status: number;
  code: ErrorCode;
  detail?: string;
  instance?: string;
  trace_id: string;
  errors?: FieldError[];
}

export function buildErrorBody(params: {
  status: number;
  code: ErrorCode;
  title: string;
  traceId: string;
  detail?: string;
  instance?: string;
  errors?: FieldError[];
}): ApiErrorBody {
  return {
    type: `https://errors.healuxa.com/${params.code}`,
    title: params.title,
    status: params.status,
    code: params.code,
    detail: params.detail,
    instance: params.instance,
    trace_id: params.traceId,
    errors: params.errors,
  };
}

export interface HealuxaHeaders {
  user?: string;
  tenant?: string;
  roles?: string[];
  permissions?: string[];
  session?: string;
}

const HEADER_USER = "x-healuxa-user";
const HEADER_TENANT = "x-healuxa-tenant";
const HEADER_ROLES = "x-healuxa-roles";
const HEADER_PERMS = "x-healuxa-perms";
const HEADER_SESSION = "x-healuxa-session";

function splitHeader(value: string | null | undefined): string[] {
  if (!value) return [];
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

export function parseHealuxaHeaders(headers: Headers): HealuxaHeaders {
  return {
    user: headers.get(HEADER_USER) ?? undefined,
    tenant: headers.get(HEADER_TENANT) ?? undefined,
    roles: splitHeader(headers.get(HEADER_ROLES)),
    permissions: splitHeader(headers.get(HEADER_PERMS)),
    session: headers.get(HEADER_SESSION) ?? undefined,
  };
}

export function requirePermission(headers: HealuxaHeaders, permission: string): void {
  if (!headers.user) {
    throw new Error("unauthorized");
  }
  if (!headers.permissions?.includes(permission)) {
    throw new Error("forbidden");
  }
}

export function getTraceId(headers: Headers): string {
  return headers.get("x-trace-id") ?? crypto.randomUUID();
}
