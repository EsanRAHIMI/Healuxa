import type { Locale } from "@healuxa/i18n";
import type { ReactNode } from "react";

import { Alert, PageHeader } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

/**
 * Editorial page rendered from catalog keys `<ns>.title`, `<ns>.lead` and `<ns>.sections.<id>.{title,body}`.
 * Bodies may contain several paragraphs separated by blank lines.
 */
export function ContentPage({
  locale,
  ns,
  sections,
  reviewNotice = false,
  children,
}: {
  locale: Locale;
  ns: string;
  sections: string[];
  reviewNotice?: boolean;
  children?: ReactNode;
}) {
  const t = getT(locale);
  return (
    <div className="hx-container py-12">
      <PageHeader title={t(`${ns}.title`)} lead={t(`${ns}.lead`)} />
      {reviewNotice ? <Alert tone="warning" role="note" className="mb-8 max-w-3xl" title={t("legal.reviewNotice")} /> : null}
      <div className="hx-prose max-w-3xl">
        {sections.map((id) => (
          <section key={id} aria-labelledby={`s-${id}`}>
            <h2 id={`s-${id}`}>{t(`${ns}.sections.${id}.title`)}</h2>
            {t(`${ns}.sections.${id}.body`)
              .split(/\n\n+/)
              .map((para, i) => (
                <p key={i}>{para}</p>
              ))}
          </section>
        ))}
        {children}
      </div>
    </div>
  );
}
