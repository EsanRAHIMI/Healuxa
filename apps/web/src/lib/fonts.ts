import { IBM_Plex_Sans_Arabic, Inter, Source_Serif_4, Vazirmatn } from "next/font/google";

import type { Locale } from "@healuxa/i18n";

// Self-hosted at build time by next/font (no runtime request to Google, CSP font-src 'self').
const inter = Inter({ subsets: ["latin"], variable: "--hx-font-sans", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--hx-font-serif", display: "swap", weight: ["400", "500", "600"] });
const arabic = IBM_Plex_Sans_Arabic({ subsets: ["arabic"], variable: "--hx-font-sans", display: "swap", weight: ["400", "500", "600"], preload: false });
const persian = Vazirmatn({ subsets: ["arabic"], variable: "--hx-font-sans", display: "swap", preload: false });

export function fontClasses(locale: Locale): string {
  if (locale === "ar") return arabic.variable;
  if (locale === "fa") return persian.variable;
  return `${inter.variable} ${serif.variable}`;
}
