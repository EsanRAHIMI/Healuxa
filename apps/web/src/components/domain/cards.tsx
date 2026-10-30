import type { Branch, Facility, Provider, ServiceOffering } from "@healuxa/api-client";
import { formatList, languageName, type Locale } from "@healuxa/i18n";
import Link from "next/link";

import { Badge, Card, buttonClass } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

import { CheckIcon } from "./badges";
import { FeeBreakdown } from "./FeeBreakdown";

export function specialtyLabel(s: string): string {
  return s.replace(/\b\p{L}/gu, (c) => c.toUpperCase());
}

export function ProviderCard({ provider, locale }: { provider: Provider; locale: Locale }) {
  const t = getT(locale);
  const authorities = [...new Set((provider.verified_credentials ?? []).map((c) => c.issuing_authority).filter((a): a is string => !!a))];
  return (
    <Card as="li" className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xl">
            <Link href={`/${locale}/providers/${provider.id}`} className="text-text no-underline hover:underline" data-testid="provider-link">
              {provider.display_name}
            </Link>
          </h3>
          {provider.title ? <p className="text-text-muted">{provider.title}</p> : null}
        </div>
        <Badge tone="neutral">{t(`enums.providerType.${provider.type}`)}</Badge>
      </div>
      {provider.specialties.length ? (
        <p className="text-sm">
          <span className="text-text-muted">{t("providers.specialties")}: </span>
          {formatList(provider.specialties.map(specialtyLabel), locale)}
        </p>
      ) : null}
      <p className="text-sm">
        <span className="text-text-muted">{t("providers.languages")}: </span>
        {formatList(provider.languages.map((l) => languageName(l, locale)), locale)}
      </p>
      {authorities.length ? (
        <p className="mt-auto flex items-center gap-1.5 text-sm text-success">
          <CheckIcon />
          {t("providers.verifiedBy", { authorities: formatList(authorities, locale) })}
        </p>
      ) : null}
    </Card>
  );
}

export function FacilityCard({ facility, locale, cities }: { facility: Facility; locale: Locale; cities?: readonly string[] }) {
  const t = getT(locale);
  return (
    <Card as="li" className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-xl">
          <Link href={`/${locale}/facilities/${facility.id}`} className="text-text no-underline hover:underline" data-testid="facility-link">
            {facility.name}
          </Link>
        </h3>
        <Badge tone="neutral">{t(`enums.facilityType.${facility.type}`)}</Badge>
      </div>
      {cities?.length ? <p className="text-sm text-text-muted">{formatList([...cities], locale)}</p> : null}
      <p className="mt-auto flex items-center gap-1.5 text-sm text-success">
        <CheckIcon />
        {t("facilities.licenceVerified")}
      </p>
    </Card>
  );
}

export function OfferingCard({
  offering,
  locale,
  provider,
  facility,
  branch,
}: {
  offering: ServiceOffering;
  locale: Locale;
  provider?: Provider;
  facility?: Facility;
  branch?: Branch;
}) {
  const t = getT(locale);
  return (
    <Card as="li" className="flex flex-col gap-3" data-testid="offering">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium tracking-wide text-accent uppercase">{specialtyLabel(offering.category)}</p>
          <h3 className="text-xl" data-testid="offering-name">
            {offering.name}
          </h3>
        </div>
        <Badge tone="neutral">{t(`enums.offeringMode.${offering.mode ?? "in_person"}`)}</Badge>
      </div>
      <p className="text-sm text-text-muted">
        {t("services.duration", { minutes: offering.duration_minutes })}
        {provider ? (
          <>
            {" · "}
            <Link href={`/${locale}/providers/${provider.id}`}>{provider.display_name}</Link>
          </>
        ) : null}
        {facility ? (
          <>
            {" · "}
            <Link href={`/${locale}/facilities/${facility.id}`}>{facility.name}</Link>
            {branch ? `, ${branch.name} (${branch.city})` : null}
          </>
        ) : null}
      </p>
      <div className="mt-auto rounded-md bg-surface-muted p-3">
        <FeeBreakdown offering={offering} locale={locale} />
      </div>
      {offering.status === "active" ? (
        <Link href={`/${locale}/book/${offering.id}`} className={buttonClass("primary", "sm", "self-start")} data-testid="book-offering">
          {t("booking.book")}
        </Link>
      ) : null}
    </Card>
  );
}
