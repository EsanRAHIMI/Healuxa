import { headers } from "next/headers";

import { jsonLd } from "@/lib/seo";

/** Structured data. Callers must only pass verified, public data (see lib/structured-data.ts). */
export async function JsonLd({ data }: { data: unknown }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return <script type="application/ld+json" nonce={nonce} dangerouslySetInnerHTML={{ __html: jsonLd(data) }} />;
}
