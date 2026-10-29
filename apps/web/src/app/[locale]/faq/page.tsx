import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }> };

const QUESTIONS = ["what", "verified", "fees", "languages", "travel", "emergency", "data", "providers"] as const;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return pageMetadata(locale, "/faq", { title: t("faq.title"), description: t("faq.lead") });
}

export default async function FaqPage({ params }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return (
    <div className="hx-container py-12">
      <PageHeader title={t("faq.title")} lead={t("faq.lead")} />
      <div className="max-w-3xl divide-y divide-border rounded-lg border border-border bg-surface">
        {QUESTIONS.map((q) => (
          <details key={q} className="group px-5 py-4">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 font-medium">
              <h2 className="font-sans text-base font-medium">{t(`faq.items.${q}.q`)}</h2>
              <span aria-hidden="true" className="text-xl text-text-muted transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <p className="mt-2 text-text-muted">{t(`faq.items.${q}.a`)}</p>
          </details>
        ))}
      </div>
    </div>
  );
}
