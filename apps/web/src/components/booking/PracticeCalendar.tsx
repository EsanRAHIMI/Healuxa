import { unwrap, type Appointment } from "@healuxa/api-client";
import { formatDate, type Locale } from "@healuxa/i18n";
import Link from "next/link";

import { ServiceError, settle } from "@/components/domain/ServiceError";
import { EmptyState, Section, buttonClass } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT } from "@/lib/i18n";

import { AppointmentActions } from "./AppointmentActions";
import { AppointmentRow } from "./AppointmentRow";

function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/**
 * Provider / facility booking calendar: pending requests to confirm, then a 7-day agenda.
 * `scope` is passed to listAppointments (provider_id or facility_id); appointment-service checks
 * that the caller owns the provider or holds facility_admin/scheduler at the facility.
 */
export async function PracticeCalendar({ scope, locale, basePath, from }: { scope: { provider_id?: string; facility_id?: string }; locale: Locale; basePath: string; from?: string }) {
  const t = getT(locale);
  const today = new Date().toISOString().slice(0, 10);
  const start = from && /^\d{4}-\d{2}-\d{2}$/.test(from) ? from : today;
  const end = addDays(start, 7);
  const api = await userApi();
  const data = await settle(async () => {
    const [requests, week] = await Promise.all([
      unwrap(api.appointment.GET("/appointments", { params: { query: { ...scope, status: "requested", limit: 100 } } })),
      unwrap(api.appointment.GET("/appointments", { params: { query: { ...scope, from: `${start}T00:00:00Z`, to: `${end}T00:00:00Z`, limit: 100 } } })),
    ]);
    return { requests: requests.data, week: week.data.filter((a) => !["held", "expired"].includes(a.status)) };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const byDay = new Map<string, Appointment[]>();
  for (const a of data.value.week) {
    const day = (a.local_start ?? a.scheduled_at).slice(0, 10);
    byDay.set(day, [...(byDay.get(day) ?? []), a]);
  }
  return (
    <>
      <Section title={t("bookings.toConfirm")} description={t("bookings.toConfirmLead")} id="requests">
        {data.value.requests.length === 0 ? (
          <EmptyState title={t("bookings.noRequests")} />
        ) : (
          <ul className="space-y-3" data-testid="booking-requests">
            {data.value.requests.map((a) => (
              <AppointmentRow key={a.id} appointment={a} locale={locale} actions={<AppointmentActions appointment={a} side="practice" locale={locale} />} />
            ))}
          </ul>
        )}
      </Section>
      <Section
        title={t("bookings.agenda")}
        id="agenda"
        actions={
          <nav aria-label={t("booking.weekNav")} className="flex gap-2">
            <Link href={`${basePath}?from=${addDays(start, -7)}`} className={buttonClass("secondary", "sm")}>
              {t("booking.prevWeek")}
            </Link>
            <Link href={`${basePath}?from=${addDays(start, 7)}`} className={buttonClass("secondary", "sm")}>
              {t("booking.nextWeek")}
            </Link>
          </nav>
        }
      >
        <p className="mb-4 text-sm text-text-muted">
          {formatDate(start, locale)} – {formatDate(addDays(end, -1), locale)}
        </p>
        {byDay.size === 0 ? (
          <EmptyState title={t("bookings.emptyWeek")} />
        ) : (
          <div className="space-y-6">
            {[...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, list]) => (
              <div key={day}>
                <h3 className="mb-2 font-sans text-base font-semibold">{formatDate(day, locale, { weekday: "long", day: "numeric", month: "long" })}</h3>
                <ul className="space-y-3">
                  {list.map((a) => (
                    <AppointmentRow key={a.id} appointment={a} locale={locale} actions={<AppointmentActions appointment={a} side="practice" locale={locale} />} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
