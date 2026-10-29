import type { Metadata } from "next";
import Link from "next/link";

import { ProviderCard } from "@/components/domain/cards";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Alert, ButtonLink, Card } from "@/components/ui/primitives";
import { searchProviders } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return pageMetadata(locale, "/", { title: t("meta.homeTitle"), description: t("meta.homeDescription") });
}

export default async function HomePage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const featured = await settle(() => searchProviders({ limit: 3 }));
  const pillars = ["verified", "transparent", "concierge"] as const;
  return (
    <>
      <section className="border-b border-border bg-surface">
        <div className="hx-container grid gap-10 py-14 md:grid-cols-[1.3fr_1fr] md:py-20">
          <div>
            {sp.signedOut ? (
              <Alert tone="success" role="status" className="mb-6" title={t("auth.signedOut")} />
            ) : null}
            <p className="mb-3 text-sm font-medium tracking-wide text-accent uppercase">{t("home.eyebrow")}</p>
            <h1 className="text-4xl leading-tight md:text-5xl">{t("home.title")}</h1>
            <p className="mt-5 max-w-xl text-lg text-text-muted">{t("home.lead")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href={`/${locale}/providers`} size="lg">
                {t("home.ctaProviders")}
              </ButtonLink>
              <ButtonLink href={`/${locale}/how-it-works`} variant="secondary" size="lg">
                {t("home.ctaHow")}
              </ButtonLink>
            </div>
          </div>
          <Card className="self-center bg-surface-muted shadow-none">
            <h2 className="text-xl">{t("home.trustTitle")}</h2>
            <ul className="mt-4 space-y-3 text-text-muted">
              <li>{t("home.trust1")}</li>
              <li>{t("home.trust2")}</li>
              <li>{t("home.trust3")}</li>
            </ul>
          </Card>
        </div>
      </section>

      <section aria-labelledby="pillars" className="hx-container py-14">
        <h2 id="pillars" className="text-3xl">
          {t("home.pillarsTitle")}
        </h2>
        <ul className="mt-8 grid gap-5 md:grid-cols-3">
          {pillars.map((p) => (
            <Card as="li" key={p}>
              <h3 className="text-xl">{t(`home.pillar.${p}.title`)}</h3>
              <p className="mt-2 text-text-muted">{t(`home.pillar.${p}.body`)}</p>
            </Card>
          ))}
        </ul>
      </section>

      <section aria-labelledby="featured" className="hx-container pb-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="featured" className="text-3xl">
            {t("home.featuredTitle")}
          </h2>
          <Link href={`/${locale}/providers`}>{t("home.featuredAll")}</Link>
        </div>
        <div className="mt-6">
          {!featured.ok ? (
            <ServiceError error={featured.error} locale={locale} />
          ) : featured.value.data.length === 0 ? (
            <p className="text-text-muted">{t("home.featuredEmpty")}</p>
          ) : (
            <ul className="grid gap-5 md:grid-cols-3">
              {featured.value.data.map((p) => (
                <ProviderCard key={p.id} provider={p} locale={locale} />
              ))}
            </ul>
          )}
        </div>
      </section>

      <section aria-labelledby="partners" className="hx-container py-14">
        <Card className="grid gap-6 md:grid-cols-[2fr_1fr] md:items-center">
          <div>
            <h2 id="partners" className="text-2xl">
              {t("home.partnersTitle")}
            </h2>
            <p className="mt-2 text-text-muted">{t("home.partnersBody")}</p>
          </div>
          <div className="flex flex-wrap gap-3 md:justify-end">
            <ButtonLink href={`/${locale}/provider`} variant="secondary">
              {t("nav.forProviders")}
            </ButtonLink>
            <ButtonLink href={`/${locale}/facility`} variant="secondary">
              {t("nav.forFacilities")}
            </ButtonLink>
          </div>
        </Card>
      </section>
    </>
  );
}
