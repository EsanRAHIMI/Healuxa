import { NotFoundError, newIdempotencyKey, unwrap } from "@healuxa/api-client";
import { formatDateTime, formatMoney } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { rescheduleAction, startPaymentAction } from "@/actions/booking";
import { AppointmentActions } from "@/components/booking/AppointmentActions";
import { HoldCountdown } from "@/components/booking/HoldCountdown";
import { SlotPicker } from "@/components/booking/SlotPicker";
import { StatusBadge } from "@/components/domain/badges";
import { settle } from "@/components/domain/ServiceError";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Alert, ButtonLink, Card, DefinitionList, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getPublicFacility, getPublicProvider, listPublicBranches } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

type Props = { params: Promise<{ locale: string; id: string }>; searchParams: Promise<Record<string, string | undefined>> };

/** Booking status page: hold countdown, submit/cancel/reschedule, payment, audit trail. */
export default async function BookingDetail({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  await requireSession(locale);
  const t = getT(locale);
  const sp = await searchParams;
  const api = await userApi();
  const a = await unwrap(api.appointment.GET("/appointments/{id}", { params: { path: { id } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const [provider, facility, branches, transitions, payments] = await Promise.all([
    getPublicProvider(a.provider_id).catch(() => null),
    getPublicFacility(a.facility_id).catch(() => null),
    listPublicBranches(a.facility_id).catch(() => []),
    settle(() => unwrap(api.appointment.GET("/appointments/{id}/transitions", { params: { path: { id } } }))),
    settle(() => unwrap(api.payment.GET("/payments", { params: { query: { subject_id: id } } }))),
  ]);
  const branch = branches.find((b) => b.id === a.branch_id);
  const tz = { timeZone: a.timezone };
  const canReschedule = a.status === "requested" || a.status === "confirmed";
  const rescheduling = qp(sp, "reschedule") === "1" && canReschedule;
  const paymentList = payments.ok ? payments.value.data : [];
  const openPayment = paymentList.find((p) => !["failed", "canceled"].includes(p.status));
  return (
    <>
      <PageHeader title={a.service_name ?? t("booking.appointment")} lead={[provider?.display_name, facility?.name, branch ? `${branch.name}, ${branch.city}` : null].filter(Boolean).join(" · ")} actions={<StatusBadge status={a.status} kind="appointmentStatus" locale={locale} />} />
      {sp.held ? <Alert tone="info" role="status" className="mb-6" title={t("booking.heldTitle")}>{t("booking.heldBody")}</Alert> : null}
      {sp.rescheduled ? <Alert tone="success" role="status" className="mb-6" title={t("booking.rescheduledTitle")} /> : null}
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <Card>
            <DefinitionList
              items={[
                { term: t("booking.when"), value: <span className="hx-ltr-nums" data-testid="booking-when">{formatDateTime(a.scheduled_at, locale, { dateStyle: "full", timeStyle: "short", ...tz })}</span> },
                { term: t("pp.timezone"), value: a.timezone },
                { term: t("pp.duration"), value: t("services.duration", { minutes: a.duration_minutes }) },
                ...(a.price ? [{ term: t("payment.total"), value: <span className="hx-ltr-nums">{formatMoney(a.price.amount_minor, a.price.currency, locale)}</span> }] : []),
                { term: t("booking.payment"), value: t(`booking.paymentStatus_${a.payment_status}`) },
                { term: t("booking.reference"), value: <span className="hx-ltr-nums break-all text-sm">{a.id}</span> },
              ]}
            />
            {a.status === "held" && a.hold_expires_at ? (
              <div className="mt-4">
                <HoldCountdown expiresAt={a.hold_expires_at} label={t("booking.holdExpiresIn")} expiredLabel={t("booking.holdExpired")} />
              </div>
            ) : null}
            {a.decline_reason ? <p className="mt-4 text-sm">{t("booking.declinedBecause", { reason: t(`booking.reason_${a.decline_reason}`) })}</p> : null}
            <div className="mt-6 flex flex-wrap gap-3">
              <AppointmentActions appointment={a} side="customer" locale={locale} />
              {canReschedule && !rescheduling ? (
                <ButtonLink href={`/${locale}/account/bookings/${a.id}?reschedule=1`} variant="secondary" size="sm">
                  {t("booking.reschedule")}
                </ButtonLink>
              ) : null}
            </div>
            {a.rescheduled_to_id ? (
              <p className="mt-4 text-sm">
                <Link href={`/${locale}/account/bookings/${a.rescheduled_to_id}`}>{t("booking.seeNewBooking")}</Link>
              </p>
            ) : null}
          </Card>
          {rescheduling ? (
            <Section title={t("booking.reschedule")} description={t("booking.rescheduleLead")} id="reschedule">
              <Card>
                <SlotPicker
                  serviceId={a.service_id}
                  locale={locale}
                  from={qp(sp, "from", 10) ?? new Date().toISOString().slice(0, 10)}
                  basePath={`/${locale}/account/bookings/${a.id}?reschedule=1`}
                  action={rescheduleAction}
                  hidden={{ appointment_id: a.id, etag: `"v${a.version}"` }}
                  submitLabel={t("booking.confirmReschedule")}
                />
              </Card>
            </Section>
          ) : null}
          <Section title={t("booking.history")} id="history">
            {transitions.ok && transitions.value.data.length ? (
              <ol className="space-y-2 text-sm">
                {transitions.value.data.map((tr) => (
                  <li key={tr.id} className="flex flex-wrap gap-2">
                    <span className="hx-ltr-nums text-text-muted">{formatDateTime(tr.occurred_at, locale, { dateStyle: "short", timeStyle: "short", ...tz })}</span>
                    <span>
                      {tr.from_status ? `${t(`enums.appointmentStatus.${tr.from_status}`)} → ` : ""}
                      {t(`enums.appointmentStatus.${tr.to_status}`)}
                    </span>
                    <span className="text-text-muted">({t(`booking.party_${tr.actor_type}`)})</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-text-muted">{t("common.none")}</p>
            )}
          </Section>
        </div>
        <Card className="h-fit">
          <h2 className="text-lg">{t("booking.payment")}</h2>
          {openPayment ? (
            <p className="mt-2 text-sm">
              <Link href={`/${locale}/account/payments/${openPayment.id}`}>{t("payments.viewPayment")}</Link> · {t(`enums.paymentStatus.${openPayment.status}`)}
            </p>
          ) : a.payment_status === "pending" && ["requested", "confirmed"].includes(a.status) ? (
            <Form action={startPaymentAction} locale={locale} hidden={{ subject_type: "appointment", subject_id: a.id, payment_key: newIdempotencyKey("pay") }} showSuccess={false} label={t("payments.payNow")}>
              <p className="mt-2 text-sm text-text-muted">{t("payments.payExplainer")}</p>
              <div className="mt-4">
                <SubmitButton pendingLabel={t("payments.preparing")}>{t("payments.payNow")}</SubmitButton>
              </div>
            </Form>
          ) : (
            <p className="mt-2 text-sm text-text-muted">{t(`booking.paymentStatus_${a.payment_status}`)}</p>
          )}
        </Card>
      </div>
    </>
  );
}
