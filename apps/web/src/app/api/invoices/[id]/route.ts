import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { cookieNames } from "@/lib/auth/tokens";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Streams payment-service's printable invoice HTML for the signed-in user. Served sandboxed (no
 * scripts, no same-origin) so third-party-rendered markup can never act as this origin.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[A-Za-z0-9-]{10,36}$/.test(id)) return new NextResponse("Not found", { status: 404 });
  const token = (await cookies()).get(cookieNames().access)?.value;
  if (!token) return new NextResponse("Sign in required", { status: 401 });
  const res = await fetch(`${env.paymentApiUrl}/invoices/${id}/document`, {
    headers: { authorization: `Bearer ${token}`, accept: "text/html" },
    cache: "no-store",
    signal: AbortSignal.timeout(env.apiTimeoutMs),
  }).catch(() => null);
  if (!res) return new NextResponse("Invoice service unavailable", { status: 503 });
  if (!res.ok) return new NextResponse(res.status === 404 ? "Not found" : "Unavailable", { status: res.status === 404 ? 404 : 502 });
  return new NextResponse(await res.text(), {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": "sandbox allow-modals allow-popups; default-src 'none'; style-src 'unsafe-inline'; img-src data:",
      "cache-control": "private, no-store",
      "x-content-type-options": "nosniff",
    },
  });
}
