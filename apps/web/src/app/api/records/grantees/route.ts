import { searchFacilities, searchProviders } from "@/lib/catalog";
import { guardRequest } from "@/lib/records";

export const dynamic = "force-dynamic";

/**
 * Name search over the public directory for the share dialog (signed-in users only). The directory has
 * no text search yet, so this filters one page of each list; profile-service re-checks the grantee.
 */
export async function GET(request: Request) {
  const guard = await guardRequest(request, { write: false });
  if (guard instanceof Response) return guard;
  const q = (new URL(request.url).searchParams.get("q") ?? "").trim().toLocaleLowerCase();
  if (q.length < 2 || q.length > 80) return Response.json({ data: [] });
  const [providers, facilities] = await Promise.all([
    searchProviders({ limit: 100 }).catch(() => ({ data: [] })),
    searchFacilities({ limit: 100 }).catch(() => ({ data: [] })),
  ]);
  const data = [
    ...providers.data.filter((p) => p.display_name.toLocaleLowerCase().includes(q)).map((p) => ({ type: "provider", id: p.id, name: p.display_name })),
    ...facilities.data.filter((f) => f.name.toLocaleLowerCase().includes(q)).map((f) => ({ type: "facility", id: f.id, name: f.name })),
  ].slice(0, 10);
  return Response.json({ data }, { headers: { "cache-control": "no-store" } });
}
