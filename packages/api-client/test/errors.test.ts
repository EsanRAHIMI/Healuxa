import { describe, expect, it } from "vitest";

import {
  ForbiddenError,
  IdempotencyConflictError,
  InternalServerError,
  RateLimitedError,
  ServiceUnavailableError,
  UnprocessableError,
  isApiError,
  normalizeProblem,
  toApiError,
} from "../src/errors";

describe("normalizeProblem", () => {
  it("passes RFC 9457 bodies through", () => {
    const p = normalizeProblem(422, {
      type: "https://errors.healuxa.com/unprocessable",
      title: "Unprocessable",
      status: 422,
      code: "unprocessable",
      detail: "Provider must be verified before activation",
      trace_id: "t",
      errors: [{ field: "status", code: "invalid", message: "Provider must be verified before activation" }],
    });
    expect(p.code).toBe("unprocessable");
    expect(p.errors).toHaveLength(1);
  });

  it("unwraps FastAPI HTTPException(detail=problem)", () => {
    const p = normalizeProblem(403, { detail: { code: "forbidden", title: "Forbidden", status: 403, detail: "Missing permission: providers:verify", trace_id: "t2" } });
    expect(p).toMatchObject({ code: "forbidden", detail: "Missing permission: providers:verify", trace_id: "t2" });
  });

  it("falls back to the status code for unknown bodies", () => {
    expect(normalizeProblem(502, "<html>Bad gateway</html>").code).toBe("internal_error");
    expect(normalizeProblem(503, null).code).toBe("service_unavailable");
    expect(normalizeProblem(404, { detail: "Not Found" })).toMatchObject({ code: "not_found", detail: "Not Found" });
  });

  it("uses X-Trace-Id when the body has none", () => {
    expect(normalizeProblem(500, {}, "hdr-trace").trace_id).toBe("hdr-trace");
  });
});

describe("toApiError", () => {
  it.each([
    [403, "forbidden", ForbiddenError],
    [409, "idempotency_conflict", IdempotencyConflictError],
    [422, "unprocessable", UnprocessableError],
    [429, "rate_limited", RateLimitedError],
    [500, "internal_error", InternalServerError],
    [503, "service_unavailable", ServiceUnavailableError],
  ])("%i %s", (status, code, Klass) => {
    const error = toApiError(status, { code, title: code, status, trace_id: "t" });
    expect(error).toBeInstanceOf(Klass);
    expect(isApiError(error, code as never)).toBe(true);
  });

  it("parses Retry-After", () => {
    const error = toApiError(429, { code: "rate_limited", title: "Too many", status: 429 }, new Headers({ "retry-after": "30" }));
    expect(error.retryAfter).toBe(30);
  });

  it("serialises to problem JSON (for server -> client boundaries)", () => {
    const error = toApiError(409, { code: "conflict", title: "Conflict", status: 409, detail: "A facility must keep at least one facility_admin", trace_id: "t" });
    expect(JSON.parse(JSON.stringify(error))).toMatchObject({ code: "conflict", status: 409, trace_id: "t" });
  });
});
