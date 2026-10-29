import type { Metadata } from "next";

import { ContentPage } from "@/components/site/ContentPage";
import { getT, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return pageMetadata(locale, "/how-it-works", { title: t("how.title"), description: t("how.lead") });
}

export default async function Page({ params }: Props) {
  const locale = await resolveLocale(params);
  return <ContentPage locale={locale} ns="how" sections={["request", "match", "coordinate", "after"]} />;
}
