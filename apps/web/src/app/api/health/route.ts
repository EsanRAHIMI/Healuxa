import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Liveness for container orchestration. `?deep=1` also probes the backends this tier depends on
 * (identity + provider) and returns 503 if any is down — use it for readiness, not liveness.
 */
export async function GET(request: Request) {
  const deep = new URL(request.url).searchParams.get("deep") === "1";
  const body: Record<string, unknown> = { status: "ok", service: "web", version: process.env.APP_VERSION ?? "dev" };
  if (!deep) return NextResponse.json(body, { headers: { "cache-control": "no-store" } });

  const probe = async (base: string | undefined) => {
    if (!base) return "unconfigured";
    try {
      const res = await fetch(`${base.replace(/\/v1\/?$/, "")}/health`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
      return res.ok ? "ok" : `http_${res.status}`;
    } catch {
      return "unreachable";
    }
  };
  const [identity, provider] = await Promise.all([probe(process.env.IDENTITY_API_URL), probe(process.env.PROVIDER_API_URL)]);
  const healthy = identity === "ok" && provider === "ok";
  return NextResponse.json({ ...body, status: healthy ? "ok" : "degraded", dependencies: { identity, provider } }, { status: healthy ? 200 : 503, headers: { "cache-control": "no-store" } });
}
