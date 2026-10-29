import type { MetadataRoute } from "next";

import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  const privatePaths = ["account", "provider", "facility", "admin", "login", "register"].flatMap((p) => ["en", "ar", "fa"].map((l) => `/${l}/${p}`));
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/api/", ...privatePaths] }],
    sitemap: `${env.siteUrl}/sitemap.xml`,
    host: env.siteUrl,
  };
}
