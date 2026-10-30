import { unwrap } from "@healuxa/api-client";
import Link from "next/link";

import { AppointmentRow } from "@/components/booking/AppointmentRow";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { EmptyState, PageHeader, ButtonLink } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

/** Customer's own appointments (appointment-service listAppointments without scope = caller's). */
export default async function MyBookings({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const sp = await searchParams;
  const past = qp(sp, "view") === "past";
  const now = new Date().toISOString();
  const api = await userApi();
  const res = await settle(() =>
    unwrap(api.appointment.GET("/appointments", { params: { query: past ? { to: now, sort: "-scheduled_at", limit: 50 } : { from: now, sort: "scheduled_at", limit: 50 } } })),
  );
  return (
    <>
      <PageHeader title={t("bookings.title")} lead={t("bookings.lead")} actions={<ButtonLink href={`/${locale}/services`} variant="secondary">{t("bookings.bookNew")}</ButtonLink>} />
      <nav aria-label={t("bookings.title")} className="mb-6 flex gap-4 text-sm">
        <Link href={`/${locale}/account/bookings`} aria-current={!past ? "page" : undefined}>{t("bookings.upcoming")}</Link>
        <Link href={`/${locale}/account/bookings?view=past`} aria-current={past ? "page" : undefined}>{t("bookings.past")}</Link>
      </nav>
      {!res.ok ? (
        <ServiceError error={res.error} locale={locale} />
      ) : res.value.data.length === 0 ? (
        <EmptyState title={t("bookings.empty")} action={<ButtonLink href={`/${locale}/services`}>{t("bookings.bookNew")}</ButtonLink>} />
      ) : (
        <ul className="space-y-3" data-testid="bookings">
          {res.value.data.map((a) => (
            <AppointmentRow key={a.id} appointment={a} locale={locale} href={`/${locale}/account/bookings/${a.id}`} />
          ))}
        </ul>
      )}
    </>
  );
}
