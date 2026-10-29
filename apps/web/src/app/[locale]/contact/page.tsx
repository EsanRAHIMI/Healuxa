import type { Metadata } from "next";

import { Alert, Card, DefinitionList, PageHeader } from "@/components/ui/primitives";
import { env } from "@/lib/env";
import { getT, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return pageMetadata(locale, "/contact", { title: t("contact.title"), description: t("contact.lead") });
}

/**
 * No support-ticket backend exists yet, so this page offers direct channels (mailto/tel) instead of
 * a form that would pretend to submit.
 */
export default async function ContactPage({ params }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const email = env.supportEmail;
  const subject = encodeURIComponent(t("contact.mailSubject"));
  const items = [
    {
      term: t("contact.email"),
      value: (
        <a href={`mailto:${email}?subject=${subject}`} className="hx-ltr-nums" data-testid="contact-email">
          {email}
        </a>
      ),
    },
  ];
  if (env.supportPhone) {
    items.push({ term: t("contact.phone"), value: <a href={`tel:${env.supportPhone.replace(/[^+\d]/g, "")}`} className="hx-ltr-nums" dir="ltr">{env.supportPhone}</a> });
  }
  if (env.supportWhatsapp) {
    items.push({
      term: t("contact.whatsapp"),
      value: (
        <a href={`https://wa.me/${env.supportWhatsapp.replace(/\D/g, "")}`} rel="noopener noreferrer" target="_blank" className="hx-ltr-nums" dir="ltr">
          {env.supportWhatsapp}
          <span className="sr-only"> {t("a11y.externalLink")}</span>
        </a>
      ),
    });
  }
  return (
    <div className="hx-container py-12">
      <PageHeader title={t("contact.title")} lead={t("contact.lead")} />
      <div className="grid max-w-4xl gap-6 md:grid-cols-[3fr_2fr]">
        <Card>
          <h2 className="text-xl">{t("contact.channelsTitle")}</h2>
          <DefinitionList className="mt-4" items={items} />
          <p className="mt-6 text-sm text-text-muted">{t("contact.hours")}</p>
          <p className="mt-2 text-sm text-text-muted">{t("contact.privacyHint")}</p>
        </Card>
        <Alert tone="danger" role="note" title={t("contact.emergencyTitle")}>
          <p>{t("legal.emergency")}</p>
        </Alert>
      </div>
    </div>
  );
}
