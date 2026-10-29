import "server-only";

import {
  NotFoundError,
  unwrap,
  type Branch,
  type Facility,
  type FacilityType,
  type OperatingHours,
  type PageMeta,
  type Provider,
  type ProviderType,
  type ServiceOffering,
} from "@healuxa/api-client";
import { cache } from "react";

import { publicApi } from "@/lib/api";

export interface Page<T> {
  data: T[];
  page: PageMeta;
}

export interface ProviderQuery {
  type?: ProviderType;
  specialty?: string;
  language?: string;
  city?: string;
  near?: string;
  radius_km?: number;
  cursor?: string;
  limit?: number;
}

const orNull = async <T>(p: Promise<T>): Promise<T | null> => {
  try {
    return await p;
  } catch (error) {
    if (error instanceof NotFoundError) return null;
    throw error;
  }
};

export const searchProviders = (q: ProviderQuery): Promise<Page<Provider>> =>
  unwrap(publicApi().provider.GET("/providers", { params: { query: { limit: 12, ...q } } }));

export const getPublicProvider = cache((id: string) => orNull(unwrap(publicApi().provider.GET("/providers/{id}", { params: { path: { id } } }))));

export const searchFacilities = (q: { type?: FacilityType; city?: string; cursor?: string; limit?: number }): Promise<Page<Facility>> =>
  unwrap(publicApi().provider.GET("/facilities", { params: { query: { limit: 12, ...q } } }));

export const getPublicFacility = cache((id: string) =>
  orNull(unwrap(publicApi().provider.GET("/facilities/{facility_id}", { params: { path: { facility_id: id } } }))),
);

export const listPublicBranches = cache(async (facilityId: string): Promise<Branch[]> => {
  const res = await orNull(unwrap(publicApi().provider.GET("/facilities/{facility_id}/branches", { params: { path: { facility_id: facilityId } } })));
  return res?.data ?? [];
});

export const getPublicHours = cache((branchId: string): Promise<OperatingHours | null> =>
  orNull(unwrap(publicApi().provider.GET("/branches/{branch_id}/operating-hours", { params: { path: { branch_id: branchId } } }))),
);

export const listPublicServices = (q: { category?: string; provider_id?: string; facility_id?: string; cursor?: string; limit?: number }): Promise<Page<ServiceOffering>> =>
  unwrap(publicApi().provider.GET("/services", { params: { query: { limit: 20, ...q } } }));

/** Names for offerings' providers/facilities/branches (deduplicated, failures tolerated). */
export async function offeringContext(offerings: ServiceOffering[]) {
  const providerIds = [...new Set(offerings.map((o) => o.provider_id))];
  const facilityIds = [...new Set(offerings.map((o) => o.facility_id).filter((x): x is string => !!x))];
  const [providers, facilities, branchLists] = await Promise.all([
    Promise.all(providerIds.map((id) => getPublicProvider(id).catch(() => null))),
    Promise.all(facilityIds.map((id) => getPublicFacility(id).catch(() => null))),
    Promise.all(facilityIds.map((id) => listPublicBranches(id).catch(() => [] as Branch[]))),
  ]);
  return {
    providers: new Map(providers.filter((p): p is Provider => !!p).map((p) => [p.id, p])),
    facilities: new Map(facilities.filter((f): f is Facility => !!f).map((f) => [f.id, f])),
    branches: new Map(branchLists.flat().map((b) => [b.id, b])),
  };
}
