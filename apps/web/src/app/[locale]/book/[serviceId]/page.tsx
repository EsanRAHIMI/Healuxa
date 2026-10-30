import { NotFoundError, unwrap } from "@healuxa/api-client";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { holdSlotAction } from "@/actions/booking";
import { SlotPicker } from "@/components/booking/SlotPicker";
import { FeeBreakdown } from "@/components/domain/FeeBreakdown";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
import { publicApi } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { getPublicFacility, getPublicProvider, listPublicBranches } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

type Props = { params: Promise<{ locale: string; serviceId: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return { title: getT(locale)("booking.title"), robots: { index: false } };
}

/** Step 1 of booking: pick a slot for a public, bookable offering; holding requires sign-in. */
export default async function BookPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const { serviceId } = await params;
  if (!/^[A-Za-z0-9-]{10,36}$/.test(serviceId)) notFound();
  const t = getT(locale);
  const offering = await unwrap(publicApi().provider.GET("/services/{service_id}", { params: { path: { service_id: serviceId } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const [provider, facility, branches, session] = await Promise.all([
    getPublicProvider(offering.provider_id),
    offering.facility_id ? getPublicFacility(offering.facility_id) : null,
    offering.facility_id ? listPublicBranches(offering.facility_id) : [],
    getSession(),
  ]);
  const branch = branches.find((b) => b.id === offering.branch_id);
  const from = qp(await searchParams, "from", 10);
  return (
    <div className="hx-container py-12">
      <PageHeader eyebrow={t("booking.title")} title={offering.name} lead={[provider?.display_name, facility?.name, branch ? `${branch.name}, ${branch.city}` : null].filter(Boolean).join(" · ")} />
      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
        <Card>
          <h2 className="mb-4 text-xl">{t("booking.chooseTime")}</h2>
          {!session ? (
            <Alert tone="info" role="note" className="mb-4" title={t("booking.signInToHold")}>
              <Link href={`/${locale}/login?next=${encodeURIComponent(`/${locale}/book/${serviceId}`)}`}>{t("auth.signIn")}</Link>
            </Alert>
          ) : null}
          <SlotPicker
            serviceId={serviceId}
            locale={locale}
            from={from && /^\d{4}-\d{2}-\d{2}$/.test(from) ? from : new Date().toISOString().slice(0, 10)}
            basePath={`/${locale}/book/${serviceId}`}
            action={holdSlotAction}
            hidden={{ service_id: serviceId }}
            submitLabel={t("booking.holdSlot")}
          />
        </Card>
        <aside className="space-y-6">
          <Card>
            <h2 className="text-lg">{t("booking.summary")}</h2>
            <p className="mt-2 text-sm text-text-muted">{t("services.duration", { minutes: offering.duration_minutes })}</p>
            <div className="mt-4">
              <FeeBreakdown offering={offering} locale={locale} />
            </div>
            <p className="mt-4 text-xs text-text-muted">{t("payment.feeBreakdownExplainer")}</p>
          </Card>
          <Card className="bg-surface-muted shadow-none">
            <h2 className="text-lg">{t("booking.howItWorks")}</h2>
            <ol className="mt-2 list-decimal space-y-1 ps-5 text-sm text-text-muted">
              <li>{t("booking.stepHold")}</li>
              <li>{t("booking.stepRequest")}</li>
              <li>{t("booking.stepConfirm")}</li>
            </ol>
          </Card>
        </aside>
      </div>
    </div>
  );
}
