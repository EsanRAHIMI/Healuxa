import { LAUNCH_LOCALES } from "@healuxa/i18n";
import type { MetadataRoute } from "next";

import { searchFacilities, searchProviders } from "@/lib/catalog";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

const STATIC = ["", "/services", "/providers", "/facilities", "/how-it-works", "/medical-travel", "/faq", "/contact", "/legal/privacy", "/legal/terms", "/legal/cookies"];
const MAX_PAGES = 50;

async function collect<T extends { id: string }>(fetchPage: (cursor?: string) => Promise<{ data: T[]; page: { next_cursor?: string | null; has_more: boolean } }>): Promise<T[]> {
  const out: T[] = [];
  let cursor: string | undefined;
  for (let i = 0; i < MAX_PAGES; i++) {
    const page = await fetchPage(cursor);
    out.push(...page.data);
    if (!page.page.has_more || !page.page.next_cursor) break;
    cursor = page.page.next_cursor;
  }
  return out;
}

function entry(path: string, lastModified?: string): MetadataRoute.Sitemap[number] {
  const languages = Object.fromEntries(LAUNCH_LOCALES.map((l) => [l, `${env.siteUrl}/${l}${path}`]));
  return { url: `${env.siteUrl}/en${path}`, lastModified, alternates: { languages } };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [providers, facilities] = await Promise.all([
    collect((cursor) => searchProviders({ cursor, limit: 100 })).catch(() => []),
    collect((cursor) => searchFacilities({ cursor, limit: 100 })).catch(() => []),
  ]);
  return [
    ...STATIC.map((p) => entry(p)),
    ...providers.map((p) => entry(`/providers/${p.id}`, p.updated_at)),
    ...facilities.map((f) => entry(`/facilities/${f.id}`)),
  ];
}
