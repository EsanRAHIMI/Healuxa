import { env } from "@/lib/env";
import { FORM_OVERHEAD_BYTES, MAX_UPLOAD_BYTES, forwardHeaders, guardRequest } from "@/lib/records";

export const dynamic = "force-dynamic";

/**
 * Record upload (BFF). The multipart body is streamed straight to profile-service — never parsed or
 * written to disk here — after the same-site + CSRF checks and a hard byte limit. profile-service
 * verifies the file type from its content, encrypts it and enforces the exact size limit.
 */
export async function POST(request: Request) {
  const guard = await guardRequest(request, { write: true });
  if (guard instanceof Response) return guard;
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data;")) return Response.json({ code: "unprocessable" }, { status: 415 });
  const limit = MAX_UPLOAD_BYTES + FORM_OVERHEAD_BYTES;
  const declared = Number(request.headers.get("content-length") ?? "NaN");
  if (Number.isFinite(declared) && declared > limit) return Response.json({ code: "too_large" }, { status: 413 });
  if (!request.body) return Response.json({ code: "unprocessable" }, { status: 422 });

  // Count bytes as they pass; abort a chunked upload that exceeds the limit.
  let seen = 0;
  const limited = request.body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        seen += chunk.byteLength;
        if (seen > limit) controller.error(new RangeError("too_large"));
        else controller.enqueue(chunk);
      },
    }),
  );
  const idempotencyKey = request.headers.get("idempotency-key");
  let upstream: Response;
  try {
    upstream = await fetch(`${env.profileApiUrl}/records`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${guard.token}`,
        "content-type": contentType,
        ...(Number.isFinite(declared) ? { "content-length": String(declared) } : {}),
        ...(idempotencyKey && /^[A-Za-z0-9_.:-]{8,128}$/.test(idempotencyKey) ? { "idempotency-key": idempotencyKey } : {}),
        ...(await forwardHeaders()),
      },
      body: limited,
      // @ts-expect-error -- Node fetch needs half duplex for a streamed request body.
      duplex: "half",
      cache: "no-store",
      signal: AbortSignal.timeout(Math.max(env.apiTimeoutMs, 60_000)),
    });
  } catch (error) {
    if (seen > limit) return Response.json({ code: "too_large" }, { status: 413 });
    console.error("[records] upload proxy failed", error);
    return Response.json({ code: "service_unavailable" }, { status: 503 });
  }
  const body = await upstream.text();
  return new Response(body, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") ?? "application/json", "cache-control": "no-store" } });
}
