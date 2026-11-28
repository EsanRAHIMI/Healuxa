import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { forwardedHeaders } from "@/lib/api";
import { cookieNames, needsRefresh, rotateRefreshToken, tokenCookies } from "@/lib/auth/tokens";
import { CsrfError, assertCsrfToken } from "@/lib/csrf";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * BFF proxy for the assistant (ai-orchestrator). The browser never calls the service: this handler
 * checks CSRF (double-submit header + same-origin), takes the access token from the httpOnly cookie
 * (rotating it if it is about to expire), opens a session when needed, and pipes the SSE reply
 * through unchanged after a leading `session` event. Message text is never logged here.
 */

const SESSION_ID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const KEY = /^[A-Za-z0-9_-]{8,128}$/;
const LOCALES = new Set(["en", "ar", "fa"]);
const MAX_BODY_CHARS = 8000;

function json(status: number, code: string, extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return NextResponse.json({ code, ...extra }, { status, headers: { "cache-control": "no-store", ...headers } });
}

function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return request.headers.get("sec-fetch-site") !== "cross-site";
  try {
    const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

async function accessToken(fwd: Record<string, string>): Promise<string | null> {
  const store = await cookies();
  const names = cookieNames();
  const current = store.get(names.access)?.value ?? null;
  if (current && !needsRefresh(current)) return current;
  const refresh = store.get(names.refresh)?.value;
  if (!refresh) return current;
  const result = await rotateRefreshToken(env.identityApiUrl, refresh, { headers: fwd, timeoutMs: env.apiTimeoutMs });
  if (!result.ok) return current;
  for (const c of tokenCookies(result.tokens)) store.set(c);
  return result.tokens.access_token;
}

async function upstreamError(res: Response, extra: Record<string, unknown> = {}) {
  const body = (await res.json().catch(() => null)) as { code?: string } | null;
  const retryAfter = res.headers.get("retry-after");
  const status = [401, 403, 404, 409, 422, 429, 503].includes(res.status) ? res.status : 502;
  return json(
    status,
    body?.code ?? "service_unavailable",
    { ...extra, ...(retryAfter ? { retry_after: Number(retryAfter) } : {}) },
    retryAfter ? { "retry-after": retryAfter } : {},
  );
}

export async function POST(request: Request) {
  if (!sameOrigin(request)) return json(403, "csrf");
  try {
    await assertCsrfToken(request.headers.get("x-hx-csrf"));
  } catch (error) {
    if (error instanceof CsrfError) return json(403, "csrf");
    throw error;
  }

  const raw = await request.text();
  if (raw.length > MAX_BODY_CHARS * 2) return json(422, "validation_error");
  let input: { session_id?: unknown; content?: unknown; locale?: unknown; idempotency_key?: unknown };
  try {
    input = JSON.parse(raw);
  } catch {
    return json(422, "validation_error");
  }
  const content = typeof input.content === "string" ? input.content.trim() : "";
  const locale = typeof input.locale === "string" && LOCALES.has(input.locale) ? input.locale : "en";
  const sessionId = typeof input.session_id === "string" && SESSION_ID.test(input.session_id) ? input.session_id : null;
  const idempotencyKey = typeof input.idempotency_key === "string" && KEY.test(input.idempotency_key) ? input.idempotency_key : null;
  if (!content || content.length > MAX_BODY_CHARS) return json(422, "validation_error");

  const fwd = await forwardedHeaders();
  const token = await accessToken(fwd);
  if (!token) return json(401, "unauthorized");
  const base = env.aiApiUrl.replace(/\/+$/, "");
  const headers = { ...fwd, authorization: `Bearer ${token}`, "content-type": "application/json" };

  let session = sessionId;
  let created = false;
  if (!session) {
    const res = await fetch(`${base}/ai/sessions`, {
      method: "POST",
      headers: { ...headers, accept: "application/json" },
      body: JSON.stringify({ locale }),
      cache: "no-store",
      signal: AbortSignal.timeout(env.apiTimeoutMs),
    }).catch(() => null);
    if (!res) return json(503, "service_unavailable");
    if (!res.ok) return upstreamError(res);
    session = ((await res.json()) as { id: string }).id;
    created = true;
  }

  const upstream = await fetch(`${base}/ai/sessions/${session}/messages`, {
    method: "POST",
    headers: { ...headers, accept: "text/event-stream", ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}) },
    body: JSON.stringify({ content }),
    cache: "no-store",
    // The browser closing the request cancels the upstream turn too.
    signal: request.signal,
  }).catch(() => null);
  if (!upstream) return json(503, "service_unavailable", created ? { session_id: session } : {});
  // A freshly opened session id is returned with errors too, so a retry reuses it.
  if (!upstream.ok || !upstream.body) return upstreamError(upstream, created ? { session_id: session } : {});

  const encoder = new TextEncoder();
  const reader = upstream.body.getReader();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(`event: session\ndata: ${JSON.stringify({ session_id: session })}\n\n`));
    },
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) controller.close();
        else controller.enqueue(value);
      } catch {
        controller.enqueue(encoder.encode(`event: error\ndata: {"code":"service_unavailable"}\n\n`));
        controller.close();
      }
    },
    cancel(reason) {
      return reader.cancel(reason);
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-store, no-transform",
      "x-accel-buffering": "no",
      "x-content-type-options": "nosniff",
    },
  });
}
