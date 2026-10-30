import type { Metadata } from "next";
import type { ReactNode } from "react";

import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { privateMetadata } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("fp.title"));
}

export default async function FacilityPortalLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  return <div className="hx-container py-10">{children}</div>;
}
