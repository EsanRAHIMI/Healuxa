import "server-only";

import { LAUNCH_LOCALES, LOCALE_INFO, type Locale } from "@healuxa/i18n";
import type { Metadata } from "next";

import { env } from "@/lib/env";
import { getT } from "@/lib/i18n";

/** `/providers` -> canonical + hreflang alternates for every launch locale (+ x-default -> en). */
export function alternates(locale: Locale, path: string): NonNullable<Metadata["alternates"]> {
  const clean = path === "/" ? "" : path;
  const languages: Record<string, string> = {};
  for (const l of LAUNCH_LOCALES) languages[l] = `${env.siteUrl}/${l}${clean}`;
  languages["x-default"] = `${env.siteUrl}/en${clean}`;
  return { canonical: `${env.siteUrl}/${locale}${clean}`, languages };
}

export function pageMetadata(
  locale: Locale,
  path: string,
  { title, description, noindex = false }: { title: string; description?: string; noindex?: boolean },
): Metadata {
  const t = getT(locale);
  return {
    title,
    description: description ?? t("meta.defaultDescription"),
    alternates: alternates(locale, path),
    robots: noindex ? { index: false, follow: false } : undefined,
    openGraph: {
      type: "website",
      siteName: t("common.appName"),
      title,
      description: description ?? t("meta.defaultDescription"),
      locale: LOCALE_INFO[locale].og,
      url: `${env.siteUrl}/${locale}${path === "/" ? "" : path}`,
    },
  };
}

/** Private portals are never indexed. */
export function privateMetadata(locale: Locale, title: string): Metadata {
  return { title, robots: { index: false, follow: false } };
}

/** Serialize JSON-LD safely for a <script> element (no `</script>` / HTML breakouts). */
export function jsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
}
