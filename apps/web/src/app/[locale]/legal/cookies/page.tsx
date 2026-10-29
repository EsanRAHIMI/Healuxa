import type { Metadata } from "next";

import { ContentPage } from "@/components/site/ContentPage";
import { getT, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return pageMetadata(locale, "/legal/cookies", { title: t("legal.cookies.title"), description: t("legal.cookies.lead") });
}

export default async function Page({ params }: Props) {
  const locale = await resolveLocale(params);
  return <ContentPage locale={locale} ns="legal.cookies" sections={["what", "essential", "preferences", "analytics", "manage"]} reviewNotice />;
}
