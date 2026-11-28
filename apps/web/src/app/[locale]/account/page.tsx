import { unwrap } from "@healuxa/api-client";
import { formatDate, formatDateTime } from "@healuxa/i18n";
import Link from "next/link";

import { deleteAccountAction } from "@/actions/account";
import { AppointmentRow } from "@/components/booking/AppointmentRow";
import { JourneyRail, Panel } from "@/components/dashboard/parts";
import { StatusBadge } from "@/components/domain/badges";
import { settle } from "@/components/domain/ServiceError";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { stepHref } from "@/components/journey/JourneyTimeline";
import { LiveRefresh } from "@/components/live/LiveRefresh";
import { ButtonLink, Card, Section, buttonClass } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { phaseLabel, stepLabel } from "@/lib/journey";
import { loadJourney } from "@/lib/journey-server";

const CLOSED_CASE_STATUSES = new Set(["completed", "cancelled"]);

/**
 * Customer home: the next step of the journey first, then upcoming visits and open concierge
 * requests, then everything else grouped by purpose. Each block loads independently so one
 * unavailable service never blanks the page.
 */
export default async function AccountPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const base = `/${locale}/account`;
  const api = await userApi();
  const now = new Date().toISOString();
  const [journeyRes, visitsRes, casesRes] = await Promise.all([
    settle(() => loadJourney(session.userId)),
    settle(() => unwrap(api.appointment.GET("/appointments", { params: { query: { from: now, sort: "scheduled_at", limit: 10 } } }))),
    settle(() => unwrap(api.concierge.GET("/concierge/cases", { params: { query: { limit: 10 } } }))),
  ]);

  const view = journeyRes.ok ? journeyRes.value : null;
  const steps = view?.phases.flatMap((p) => p.milestones) ?? [];
  const done = steps.filter((s) => s.status === "completed").length;
  const current = view?.phases.find((p) => p.status === "in_progress");
  const next = current?.milestones.find((s) => s.status === "pending");
  const booked = current?.milestones.find((s) => s.status === "scheduled");
  const nextHref = next ? stepHref(locale, next) : null;

  const visits = visitsRes.ok ? visitsRes.value.data.filter((a) => ["held", "requested", "confirmed", "checked_in"].includes(a.status)).slice(0, 3) : [];
  const cases = casesRes.ok ? casesRes.value.data.filter((c) => !CLOSED_CASE_STATUSES.has(c.status)).slice(0, 3) : [];

  const isStaff = ["providers:verify", "facilities:verify", "concierge:coordinate", "payments:manage", "payments:refund", "finance:reconcile"].some((p) => hasPermission(session, p));
  const groups = [
    {
      title: t("dash.groupCare"),
      links: [
        { href: `/${locale}/journey`, label: t("journey.title") },
        { href: `${base}/bookings`, label: t("bookings.title") },
        { href: `${base}/records`, label: t("records.title") },
        { href: `/${locale}/services`, label: t("nav.services") },
      ],
    },
    {
      title: t("dash.groupMessages"),
      links: [
        { href: `${base}/concierge`, label: t("concierge.title") },
        { href: `${base}/notifications`, label: t("notifications.title") },
      ],
    },
    { title: t("dash.groupBilling"), links: [{ href: `${base}/payments`, label: t("payments.title") }] },
    {
      title: t("dash.groupSettings"),
      links: [
        { href: `${base}/profile`, label: t("account.privacyPrefs") },
        { href: `${base}/sessions`, label: t("account.sessions") },
      ],
    },
  ];
  const workspaces = [
    ...(hasPermission(session, "providers:onboard") ? [{ href: `/${locale}/provider`, label: t("nav.forProviders") }] : []),
    ...(hasPermission(session, "facilities:onboard") ? [{ href: `/${locale}/facility`, label: t("nav.forFacilities") }] : []),
    ...(isStaff ? [{ href: `/${locale}/admin`, label: t("nav.admin") }] : []),
  ];

  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl md:text-4xl">{t("dash.greeting")}</h1>
        <LiveRefresh label={t("live.on")} />
      </header>

      <section
        aria-labelledby="next-title"
        className="rounded-2xl bg-primary p-6 text-on-primary md:p-8"
        style={{ ["--rail-bg" as string]: "var(--hx-color-primary)" }}
        data-testid="dash-next"
      >
        {view ? (
          <div className="grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center">
            <div>
              <p id="next-title" className="text-sm opacity-80">
                {t("dash.nextStep")}
              </p>
              <p className="mt-2 font-serif text-2xl leading-snug md:text-3xl">
                {next ? stepLabel(t, next) : booked ? stepLabel(t, booked) : t("dash.allDone")}
              </p>
              {!next && booked?.scheduled_at ? (
                <p className="mt-2 opacity-90">{t("dash.booked", { date: formatDateTime(booked.scheduled_at, locale, { dateStyle: "medium", timeStyle: "short" }) })}</p>
              ) : null}
              <div className="mt-5 flex flex-wrap gap-3">
                {next && nextHref ? (
                  <Link href={nextHref} className={buttonClass("secondary", "md", "border-transparent")} data-testid="dash-continue">
                    {t("dash.continue")}
                  </Link>
                ) : null}
                <Link href={`/${locale}/journey`} className="inline-flex min-h-11 items-center px-1 font-medium text-on-primary underline underline-offset-4">
                  {t("dash.viewJourney")}
                </Link>
              </div>
            </div>
            <div>
              <JourneyRail stages={view.phases.map((p) => ({ key: p.id, label: phaseLabel(t, p), status: p.status }))} />
              <p className="mt-4 text-center text-sm opacity-80">{t("dash.progress", { done, total: steps.length })}</p>
            </div>
          </div>
        ) : (
          <div className="max-w-2xl">
            <h2 id="next-title" className="text-2xl md:text-3xl">
              {t("dash.startTitle")}
            </h2>
            <p className="mt-2 opacity-90">{t("dash.startBody")}</p>
            <div className="mt-5">
              <Link href={`/${locale}/journey`} className={buttonClass("secondary", "md", "border-transparent")} data-testid="dash-start">
                {t("dash.start")}
              </Link>
            </div>
          </div>
        )}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel id="visits" title={t("dash.upcoming")} href={`${base}/bookings`} linkLabel={t("dash.viewAll")}>
          {visits.length === 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-text-muted">{t("dash.noUpcoming")}</p>
              <ButtonLink href={`/${locale}/services`} variant="secondary" size="sm">
                {t("dash.findCare")}
              </ButtonLink>
            </div>
          ) : (
            <ul className="space-y-3" data-testid="dash-visits">
              {visits.map((a) => (
                <AppointmentRow key={a.id} appointment={a} locale={locale} href={`${base}/bookings/${a.id}`} />
              ))}
            </ul>
          )}
        </Panel>
        <Panel id="cases" title={t("dash.concierge")} href={`${base}/concierge`} linkLabel={t("dash.viewAll")}>
          {cases.length === 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-text-muted">{t("dash.noCases")}</p>
              <ButtonLink href={`${base}/concierge#new`} variant="secondary" size="sm">
                {t("dash.askConcierge")}
              </ButtonLink>
            </div>
          ) : (
            <ul className="divide-y divide-border" data-testid="dash-cases">
              {cases.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div>
                    <Link href={`${base}/concierge/${c.id}`} className="font-medium">
                      {t(`enums.caseCategory.${c.category}`)}
                    </Link>
                    <p className="text-sm text-text-muted">{t("dash.opened", { date: formatDate(c.created_at, locale) })}</p>
                  </div>
                  <StatusBadge status={c.status} kind="caseStatus" locale={locale} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <section aria-labelledby="manage-title" className="mt-10">
        <h2 id="manage-title" className="mb-4 text-2xl">
          {t("dash.manage")}
        </h2>
        <div className="grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
          {[...groups, ...(workspaces.length ? [{ title: t("dash.workspaces"), links: workspaces }] : [])].map((g) => (
            <div key={g.title}>
              <h3 className="mb-2 font-sans text-sm font-semibold text-text-muted">{g.title}</h3>
              <ul className="space-y-1">
                {g.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="inline-flex min-h-9 items-center font-medium text-text no-underline hover:text-primary">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <Section title={t("account.deleteTitle")} description={t("account.deleteLead")} id="delete">
        <Card className="max-w-xl">
          <Form action={deleteAccountAction} locale={locale} label={t("account.deleteTitle")} showSuccess={false} testId="delete-account-form">
            <div className="space-y-4">
              <TextField name="password" type="password" label={t("auth.password")} required requiredLabel={t("common.required")} autoComplete="current-password" />
              <TextField name="confirm_text" label={t("account.deleteConfirmLabel")} hint={t("account.deleteConfirmHint")} required requiredLabel={t("common.required")} autoComplete="off" dir="ltr" />
              <ConfirmButton trigger={t("account.deleteButton")} title={t("account.deleteTitle")} description={t("account.deleteWarning")} confirmLabel={t("account.deleteButton")} cancelLabel={t("common.cancel")} name="confirm" value="1" />
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
