import { env } from "@/lib/env";
import { ID_RE, forwardHeaders, guardRequest } from "@/lib/records";

export const dynamic = "force-dynamic";

const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);

/**
 * Authenticated download (owner or an active grantee — profile-service decides and logs every attempt).
 * Streamed through as an attachment; never inline, never cached.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!ID_RE.test(id)) return new Response("Not found", { status: 404 });
  const guard = await guardRequest(request, { write: false });
  if (guard instanceof Response) return guard;
  const upstream = await fetch(`${env.profileApiUrl}/records/${id}/content`, {
    headers: { authorization: `Bearer ${guard.token}`, ...(await forwardHeaders()) },
    cache: "no-store",
    signal: AbortSignal.timeout(Math.max(env.apiTimeoutMs, 60_000)),
  }).catch(() => null);
  if (!upstream) return new Response("Unavailable", { status: 503 });
  if (!upstream.ok || !upstream.body) {
    const status = [401, 403, 404].includes(upstream.status) ? upstream.status : 502;
    return new Response(status === 403 ? "Access ended" : status === 404 ? "Not found" : "Unavailable", { status, headers: { "cache-control": "no-store" } });
  }
  const type = upstream.headers.get("content-type") ?? "";
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": ALLOWED_TYPES.has(type) ? type : "application/octet-stream",
      "content-disposition": upstream.headers.get("content-disposition") ?? "attachment",
      "x-content-type-options": "nosniff",
      "cache-control": "private, no-store",
      "content-security-policy": "default-src 'none'; sandbox",
    },
  });
}
