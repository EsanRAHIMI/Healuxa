import { unwrap } from "@healuxa/api-client";
import { formatMoney, formatNumber, type Locale } from "@healuxa/i18n";

import { AppointmentActions } from "@/components/booking/AppointmentActions";
import { AppointmentRow } from "@/components/booking/AppointmentRow";
import { Breakdown, Panel, Stat, StatRow } from "@/components/dashboard/parts";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { LiveRefresh } from "@/components/live/LiveRefresh";
import { userApi } from "@/lib/api";
import { getT } from "@/lib/i18n";

const DAY = 86_400_000;
const SEGMENTS = [
  { key: "completed", className: "bg-success" },
  { key: "confirmed", className: "bg-primary" },
  { key: "checked_in", className: "bg-info" },
  { key: "requested", className: "bg-warning" },
  { key: "cancelled", className: "bg-border-strong" },
  { key: "declined", className: "bg-border-strong" },
  { key: "no_show", className: "bg-danger" },
] as const;

/**
 * Live operational view for a practitioner or a facility: what needs an answer now, today's
 * schedule, and a 30-day performance report. Figures come from appointment-service
 * (`/appointments/summary`), which applies the caller's calendar access rules.
 */
export async function PracticeDashboard({ scope, locale, calendarHref }: { scope: { provider_id?: string; facility_id?: string }; locale: Locale; calendarHref: string }) {
  const t = getT(locale);
  const api = await userApi();
  const now = new Date();
  const dayStart = new Date(now);
  dayStart.setUTCHours(0, 0, 0, 0);
  // "Today" spans the local day of any UAE-adjacent zone: look from the previous UTC midnight to +36h and filter by local date.
  const iso = (d: Date) => d.toISOString();
  const data = await settle(async () => {
    const [requests, soon, week, report] = await Promise.all([
      unwrap(api.appointment.GET("/appointments", { params: { query: { ...scope, status: "requested", limit: 50 } } })),
      unwrap(api.appointment.GET("/appointments", { params: { query: { ...scope, from: iso(new Date(dayStart.getTime() - DAY)), to: iso(new Date(dayStart.getTime() + 2 * DAY)), limit: 100 } } })),
      unwrap(api.appointment.GET("/appointments/summary", { params: { query: { ...scope, from: iso(now), to: iso(new Date(now.getTime() + 7 * DAY)) } } })),
      unwrap(api.appointment.GET("/appointments/summary", { params: { query: { ...scope, from: iso(new Date(now.getTime() - 30 * DAY)), to: iso(now) } } })),
    ]);
    return { requests: requests.data, soon: soon.data, week, report };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const { requests, soon, week, report } = data.value;

  const today = soon.filter((a) => {
    if (["held", "expired", "cancelled", "declined"].includes(a.status)) return false;
    const localToday = new Intl.DateTimeFormat("en-CA", { timeZone: a.timezone, dateStyle: "short" }).format(now);
    return (a.local_start ?? a.scheduled_at).slice(0, 10) === localToday;
  });
  const by = report.by_status;
  const completed = by.completed ?? 0;
  const closed = completed + (by.cancelled ?? 0) + (by.no_show ?? 0) + (by.declined ?? 0);
  const upcoming = (week.by_status.confirmed ?? 0) + (week.by_status.requested ?? 0);

  return (
    <div className="space-y-6" data-testid="practice-dashboard">
      <div className="flex justify-end">
        <LiveRefresh label={t("live.on")} />
      </div>
      <section aria-label={t("dash.practice.today")} className="rounded-xl border border-border bg-surface p-5 md:p-6">
        <StatRow>
          <Stat label={t("dash.practice.toConfirm")} value={formatNumber(requests.length, locale)} tone={requests.length ? "attention" : "default"} />
          <Stat label={t("dash.practice.today")} value={formatNumber(today.length, locale)} />
          <Stat label={t("dash.practice.nextWeek")} value={formatNumber(upcoming, locale)} />
          <Stat
            label={t("dash.practice.completionRate")}
            value={closed ? `${formatNumber(Math.round((completed / closed) * 100), locale)}%` : "—"}
            hint={t("dash.practice.last30")}
          />
        </StatRow>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel id="requests" title={t("dash.practice.requestsTitle")} href={calendarHref} linkLabel={t("dash.practice.openCalendar")}>
          {requests.length === 0 ? (
            <p className="text-text-muted">{t("dash.practice.noRequests")}</p>
          ) : (
            <ul className="space-y-3" data-testid="dash-requests">
              {requests.slice(0, 5).map((a) => (
                <AppointmentRow key={a.id} appointment={a} locale={locale} actions={<AppointmentActions appointment={a} side="practice" locale={locale} />} />
              ))}
            </ul>
          )}
        </Panel>
        <Panel id="today" title={t("dash.practice.todayTitle")} href={calendarHref} linkLabel={t("dash.practice.openCalendar")}>
          {today.length === 0 ? (
            <p className="text-text-muted">{t("dash.practice.noToday")}</p>
          ) : (
            <ul className="space-y-3" data-testid="dash-today">
              {today.map((a) => (
                <AppointmentRow key={a.id} appointment={a} locale={locale} actions={<AppointmentActions appointment={a} side="practice" locale={locale} />} />
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel id="report" title={`${t("dash.practice.byStatus")} — ${t("dash.practice.last30")}`}>
        <div className="grid gap-6 md:grid-cols-[2fr_1fr] md:items-end">
          <Breakdown
            total={report.total}
            emptyLabel={t("dash.practice.noData")}
            items={SEGMENTS.map((s) => ({ ...s, label: t(`enums.appointmentStatus.${s.key}`), count: by[s.key] ?? 0 }))}
          />
          <StatRow className="md:grid-flow-row md:auto-cols-auto">
            <Stat
              label={t("dash.practice.revenue")}
              value={report.completed_revenue.length ? report.completed_revenue.map((m) => formatMoney(m.amount_minor, m.currency, locale)).join(" + ") : "—"}
            />
          </StatRow>
        </div>
      </Panel>
    </div>
  );
}
