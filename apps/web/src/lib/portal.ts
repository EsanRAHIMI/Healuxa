import "server-only";

import { NotFoundError, unwrap, unwrapResponse, type Branch, type Facility, type Provider } from "@healuxa/api-client";
import { cache } from "react";

import { userApi } from "@/lib/api";

/** The signed-in user's provider profile (+ ETag for If-Match), or null if they have not applied. */
export const getMyProvider = cache(async (): Promise<{ provider: Provider; etag: string } | null> => {
  const api = await userApi();
  try {
    const me = await unwrap(api.provider.GET("/providers/me"));
    // /providers/me has no ETag; read the resource to get one (version is also in the body).
    const res = await unwrapResponse(api.provider.GET("/providers/{id}", { params: { path: { id: me.id } } }));
    return { provider: res.data, etag: res.etag ?? `"v${res.data.version}"` };
  } catch (error) {
    if (error instanceof NotFoundError) return null;
    throw error;
  }
});

/** Facility as visible to the current user (private view for its staff), or null. */
export const getFacilityAs = cache(async (id: string): Promise<Facility | null> => {
  const api = await userApi();
  try {
    return await unwrap(api.provider.GET("/facilities/{facility_id}", { params: { path: { facility_id: id } } }));
  } catch (error) {
    if (error instanceof NotFoundError) return null;
    throw error;
  }
});

export const getBranchesAs = cache(async (facilityId: string): Promise<Branch[]> => {
  const api = await userApi();
  try {
    return (await unwrap(api.provider.GET("/facilities/{facility_id}/branches", { params: { path: { facility_id: facilityId } } }))).data;
  } catch (error) {
    if (error instanceof NotFoundError) return [];
    throw error;
  }
});

/** Branch label lookup for a set of facility ids (tolerates facilities the user cannot see). */
export async function branchLabels(facilityIds: string[]): Promise<Map<string, { facility: string; branch: Branch }>> {
  const out = new Map<string, { facility: string; branch: Branch }>();
  await Promise.all(
    [...new Set(facilityIds)].map(async (fid) => {
      const [facility, branches] = await Promise.all([getFacilityAs(fid).catch(() => null), getBranchesAs(fid).catch(() => [])]);
      for (const b of branches) out.set(b.id, { facility: facility?.name ?? fid, branch: b });
    }),
  );
  return out;
}
