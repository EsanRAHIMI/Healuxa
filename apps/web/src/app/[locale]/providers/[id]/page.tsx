import { formatDate, formatList, languageName } from "@healuxa/i18n";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CheckIcon } from "@/components/domain/badges";
import { OfferingCard, specialtyLabel } from "@/components/domain/cards";
import { JsonLd } from "@/components/domain/JsonLd";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Badge, ButtonLink, Card, DefinitionList, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { getPublicProvider, listPublicServices, offeringContext } from "@/lib/catalog";
import { env } from "@/lib/env";
import { getT, localized, resolveLocale } from "@/lib/i18n";
import { pageMetadata } from "@/lib/seo";
import { providerStructuredData } from "@/lib/structured-data";

type Props = { params: Promise<{ locale: string; id: string }> };

const safeId = (id: string) => (/^[A-Za-z0-9-]{10,36}$/.test(id) ? id : null);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  const provider = safeId(id) ? await getPublicProvider(id).catch(() => null) : null;
  if (!provider) return { title: t("errors.notFoundTitle"), robots: { index: false } };
  const description = [provider.title, provider.specialties.map(specialtyLabel).join(", ")].filter(Boolean).join(" · ");
  return pageMetadata(locale, `/providers/${provider.id}`, { title: provider.display_name, description: description || t("providers.lead") });
}

export default async function ProviderProfilePage({ params }: Props) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  const t = getT(locale);
  if (!safeId(id)) notFound();
  const provider = await getPublicProvider(id);
  if (!provider) notFound();

  const offerings = await settle(async () => {
    const page = await listPublicServices({ provider_id: provider.id, limit: 50 });
    return { page, ctx: await offeringContext(page.data) };
  });
  const bio = localized(provider.bio ?? null, locale);
  const url = `${env.siteUrl}/${locale}/providers/${provider.id}`;
  const ld = providerStructuredData(provider, url, provider.languages.map((l) => languageName(l, "en")));
  const credentials = provider.verified_credentials ?? [];

  return (
    <div className="hx-container py-12">
      {ld ? <JsonLd data={ld} /> : null}
      <nav aria-label={t("a11y.breadcrumb")} className="mb-6 text-sm">
        <ol className="flex flex-wrap gap-2 text-text-muted">
          <li>
            <Link href={`/${locale}/providers`}>{t("providers.title")}</Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page">{provider.display_name}</li>
        </ol>
      </nav>
      <PageHeader
        eyebrow={t(`enums.providerType.${provider.type}`)}
        title={provider.display_name}
        lead={provider.title ?? undefined}
        actions={
          <ButtonLink href={`/${locale}/contact`} variant="primary">
            {t("profile.contactConcierge")}
          </ButtonLink>
        }
      />
      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
        <div>
          {bio ? (
            <Section title={t("profile.about")} id="about">
              <p className="max-w-prose whitespace-pre-line" lang={provider.bio?.[locale] ? locale : "en"}>
                {bio}
              </p>
            </Section>
          ) : null}
          <Section title={t("profile.offerings")} description={t("payment.feeBreakdownExplainer")} id="offerings">
            {!offerings.ok ? (
              <ServiceError error={offerings.error} locale={locale} />
            ) : offerings.value.page.data.length === 0 ? (
              <EmptyState title={t("profile.noOfferings")} body={t("profile.noOfferingsBody")} />
            ) : (
              <ul className="grid gap-4 md:grid-cols-2">
                {offerings.value.page.data.map((o) => (
                  <OfferingCard
                    key={o.id}
                    offering={o}
                    locale={locale}
                    facility={o.facility_id ? offerings.value.ctx.facilities.get(o.facility_id) : undefined}
                    branch={offerings.value.ctx.branches.get(o.branch_id)}
                  />
                ))}
              </ul>
            )}
            <p className="mt-4 text-sm text-text-muted">{t("profile.bookingNote")}</p>
          </Section>
        </div>
        <aside className="space-y-6">
          <Card>
            <h2 className="text-xl">{t("profile.credentials")}</h2>
            {credentials.length === 0 ? (
              <p className="mt-2 text-text-muted">{t("profile.noCredentials")}</p>
            ) : (
              <ul className="mt-4 space-y-4" data-testid="verified-credentials">
                {credentials.map((c, i) => (
                  <li key={i} className="flex gap-3">
                    <CheckIcon className="mt-1 size-5 shrink-0 text-success" />
                    <div>
                      <p className="font-medium">{t(`enums.credentialKind.${c.kind}`)}</p>
                      <p className="text-sm text-text-muted">
                        {t("profile.issuedBy", { authority: c.issuing_authority ?? "" })}
                        {c.valid_until ? ` · ${t("profile.validUntil", { date: formatDate(c.valid_until, locale) })}` : ""}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-4 text-xs text-text-muted">{t("clinical.verifiedCredentialsExplainer")}</p>
          </Card>
          <Card>
            <DefinitionList
              items={[
                {
                  term: t("providers.specialties"),
                  value: provider.specialties.length ? formatList(provider.specialties.map(specialtyLabel), locale) : t("common.notProvided"),
                },
                {
                  term: t("providers.languages"),
                  value: (
                    <span className="flex flex-wrap gap-1.5" data-testid="provider-languages">
                      {provider.languages.map((l) => (
                        <Badge key={l} tone="primary">
                          {languageName(l, locale)}
                        </Badge>
                      ))}
                    </span>
                  ),
                },
              ]}
            />
          </Card>
        </aside>
      </div>
    </div>
  );
}
