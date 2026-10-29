import { describe, expect, it, vi } from "vitest";

import {
  ConflictError,
  NetworkError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
  createHealuxaClient,
  idempotencyHeader,
  newIdempotencyKey,
  singleFlight,
  unwrap,
  unwrapResponse,
} from "../src/index";

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });

const problem = (status: number, code: string, detail = "x") => ({
  type: `https://errors.healuxa.com/${code}`,
  title: code,
  status,
  code,
  detail,
  trace_id: "trace-1",
});

describe("createHealuxaClient", () => {
  it("prefixes the per-service base URL, sends JSON and injects the bearer token", async () => {
    const seen: Request[] = [];
    const client = createHealuxaClient({
      baseUrls: { provider: "http://provider.test/v1/" },
      auth: { getAccessToken: () => "tok-1" },
      headers: { "Accept-Language": "ar" },
      fetch: async (req) => {
        seen.push(req);
        return json(200, { data: [], page: { limit: 5, has_more: false, next_cursor: null } });
      },
    });
    const page = await unwrap(client.provider.GET("/providers", { params: { query: { specialty: "cardiology", limit: 5 } } }));
    expect(page.data).toEqual([]);
    expect(seen[0]!.url).toBe("http://provider.test/v1/providers?specialty=cardiology&limit=5");
    expect(seen[0]!.headers.get("authorization")).toBe("Bearer tok-1");
    expect(seen[0]!.headers.get("accept-language")).toBe("ar");
  });

  it("omits Authorization for anonymous callers", async () => {
    let auth: string | null = "unset";
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      fetch: async (req) => {
        auth = req.headers.get("authorization");
        return json(200, { data: [], page: { limit: 20, has_more: false } });
      },
    });
    await unwrap(client.provider.GET("/facilities"));
    expect(auth).toBeNull();
  });

  it("throws when a service base URL is missing", () => {
    const client = createHealuxaClient({ baseUrls: {} });
    expect(() => client.identity).toThrow(/no base URL configured for "identity"/);
  });

  it("refreshes once on 401 and retries with the rotated token, replaying the body", async () => {
    let token = "old";
    const refresh = vi.fn(async () => {
      token = "new";
      return "new";
    });
    const bodies: string[] = [];
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      auth: { getAccessToken: () => token, refresh },
      fetch: async (req) => {
        bodies.push(await req.text());
        return req.headers.get("authorization") === "Bearer new"
          ? json(201, { id: "c1" })
          : json(401, { detail: problem(401, "unauthorized") });
      },
    });
    const created = await unwrap(
      client.provider.POST("/providers/{id}/credentials", {
        params: { path: { id: "p1" } },
        body: { kind: "professional_license", issuing_authority: "DHA", number: "123456" },
      }),
    );
    expect(created).toEqual({ id: "c1" });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(bodies).toHaveLength(2);
    expect(JSON.parse(bodies[1]!)).toMatchObject({ number: "123456" });
  });

  it("shares one refresh between concurrent 401s (refresh-token reuse would revoke the session)", async () => {
    let token = "old";
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const refresh = vi.fn(async () => {
      await gate;
      token = "new";
      return "new";
    });
    const client = createHealuxaClient({
      baseUrls: { identity: "http://i/v1" },
      auth: { getAccessToken: () => token, refresh },
      fetch: async (req) =>
        req.headers.get("authorization") === "Bearer new"
          ? json(200, { data: [], page: { limit: 20, has_more: false } })
          : json(401, problem(401, "unauthorized")),
    });
    const calls = [unwrap(client.identity.GET("/sessions")), unwrap(client.identity.GET("/sessions")), unwrap(client.identity.GET("/sessions"))];
    await new Promise((r) => setTimeout(r, 10));
    release();
    await Promise.all(calls);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("reports session expiry when refresh fails", async () => {
    const onSessionExpired = vi.fn();
    const client = createHealuxaClient({
      baseUrls: { identity: "http://i/v1" },
      auth: { getAccessToken: () => "old", refresh: async () => null, onSessionExpired },
      fetch: async () => json(401, problem(401, "unauthorized", "Missing or invalid token")),
    });
    await expect(unwrap(client.identity.GET("/sessions"))).rejects.toBeInstanceOf(UnauthorizedError);
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it("passes requestInitExt (e.g. Next.js revalidate) as fetch's second argument", async () => {
    let init: unknown;
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      requestInitExt: { next: { revalidate: 60 } },
      fetch: async (_req, i) => {
        init = i;
        return json(200, { data: [], page: { limit: 20, has_more: false } });
      },
    });
    await unwrap(client.provider.GET("/services"));
    expect(init).toEqual({ next: { revalidate: 60 } });
  });

  it("exposes the ETag for optimistic concurrency", async () => {
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      fetch: async () => json(200, { id: "p1", version: 3 }, { etag: '"v3"' }),
    });
    const { etag } = await unwrapResponse(client.provider.GET("/providers/{id}", { params: { path: { id: "p1" } } }));
    expect(etag).toBe('"v3"');
  });

  it("maps errors to typed classes", async () => {
    const responses = [json(404, problem(404, "not_found", "Provider not found")), json(409, problem(409, "conflict"))];
    const client = createHealuxaClient({ baseUrls: { provider: "http://p/v1" }, fetch: async () => responses.shift()! });
    const missing = await unwrap(client.provider.GET("/providers/{id}", { params: { path: { id: "x" } } })).catch((e) => e);
    expect(missing).toBeInstanceOf(NotFoundError);
    expect(missing.detail).toBe("Provider not found");
    expect(missing.traceId).toBe("trace-1");
    await expect(unwrap(client.provider.GET("/providers/{id}", { params: { path: { id: "x" } } }))).rejects.toBeInstanceOf(ConflictError);
  });

  it("maps a network failure to NetworkError", async () => {
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      fetch: async () => {
        throw new TypeError("fetch failed");
      },
    });
    const error = await unwrap(client.provider.GET("/services")).catch((e) => e);
    expect(error).toBeInstanceOf(NetworkError);
    expect(error.code).toBe("network_error");
    expect(error.status).toBe(0);
  });

  it("surfaces FastAPI request-validation errors as ValidationError with field errors", async () => {
    const client = createHealuxaClient({
      baseUrls: { provider: "http://p/v1" },
      fetch: async () =>
        json(422, { detail: [{ type: "string_too_short", loc: ["body", "display_name"], msg: "String should have at least 2 characters" }] }),
    });
    const error = await unwrap(
      client.provider.POST("/providers", { body: { type: "doctor", display_name: "x", specialties: ["a"], languages: ["en"] } }),
    ).catch((e) => e);
    expect(error).toBeInstanceOf(ValidationError);
    expect(error.fieldMessage("display_name")).toBe("String should have at least 2 characters");
  });
});

describe("idempotency helpers", () => {
  it("generates unique, valid keys", () => {
    const keys = new Set(Array.from({ length: 50 }, () => newIdempotencyKey("reg")));
    expect(keys.size).toBe(50);
    for (const key of keys) expect(key).toMatch(/^reg-[0-9a-f-]{36}$/);
  });

  it("falls back when crypto.randomUUID is unavailable (React Native)", () => {
    const original = globalThis.crypto.randomUUID;
    Object.defineProperty(globalThis.crypto, "randomUUID", { value: undefined, configurable: true });
    try {
      expect(newIdempotencyKey()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    } finally {
      Object.defineProperty(globalThis.crypto, "randomUUID", { value: original, configurable: true });
    }
  });

  it("rejects malformed caller keys", () => {
    expect(() => idempotencyHeader("short")).toThrow(RangeError);
    expect(idempotencyHeader("abcdefgh-1234")).toEqual({ "Idempotency-Key": "abcdefgh-1234" });
  });
});

describe("singleFlight", () => {
  it("allows a new call after the previous settles", async () => {
    let n = 0;
    const once = singleFlight(async () => ++n);
    expect(await Promise.all([once(), once()])).toEqual([1, 1]);
    expect(await once()).toBe(2);
  });
});
