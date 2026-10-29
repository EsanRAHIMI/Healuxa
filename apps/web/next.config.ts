import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * Static security headers. The Content-Security-Policy is per-request (nonce) and set in src/proxy.ts.
 */
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(self), payment=(), usb=(), interest-cohort=(), browsing-topics=()",
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  // Monorepo: trace workspace packages from the repo root so the standalone bundle is complete.
  outputFileTracingRoot: path.join(here, "../.."),
  turbopack: { root: path.join(here, "../..") },
  transpilePackages: ["@healuxa/api-client", "@healuxa/design-tokens", "@healuxa/i18n"],
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: false,
  experimental: {
    serverActions: {
      bodySizeLimit: "256kb",
      // Behind Traefik the Host header is the public host; list extra trusted origins (CDN, preview) here.
      allowedOrigins: process.env.SERVER_ACTIONS_ALLOWED_ORIGINS?.split(",").filter(Boolean) ?? [],
    },
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
