"use server";

/**
 * Booking + payment mutations (appointment-service, payment-service).
 * Flow: slot -> hold (`held`, short TTL) -> submit (`requested`) -> provider/facility accept
 * (`confirmed`) -> check_in/complete. Amounts are always quoted server-side by payment-service.
 */
import { idempotencyHeader, unwrap, unwrapResponse, type AppointmentTransitionRequest } from "@healuxa/api-client";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;
const TRANSITIONS = ["submit", "accept", "decline", "cancel", "check_in", "complete", "no_show"] as const;
type Transition = (typeof TRANSITIONS)[number];
const REASONS = ["no_capacity", "out_of_scope", "schedule_conflict", "customer_request", "provider_unavailable", "facility_closed", "other"] as const;

export async function holdSlotAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    const t = getT(locale);
    const serviceId = str(fd, "service_id");
    const slot = str(fd, "slot");
    if (!ISO.test(slot)) return invalid(locale, { slot: t("booking.errSlot") });
    const { getSession } = await import("@/lib/auth/session");
    if (!(await getSession())) {
      target = `/${locale}/login?next=${encodeURIComponent(`/${locale}/book/${serviceId}`)}`;
      return;
    }
    const api = await userApi();
    const appt = await unwrap(
      api.appointment.POST("/appointments", {
        params: { header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
        body: { service_id: serviceId, scheduled_at: slot, channel: "web" },
      }),
    );
    target = `/${locale}/account/bookings/${appt.id}?held=1`;
  }, (locale) => ({ conflict: getT(locale)("booking.slotTaken"), unprocessable: getT(locale)("booking.slotUnavailable") }));
  if (state.ok && target) redirect(target);
  return state;
}

/** Any lifecycle transition; actor rules are enforced by appointment-service. */
export async function transitionAppointmentAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const id = str(fd, "appointment_id");
    const transition = str(fd, "transition") as Transition;
    if (!TRANSITIONS.includes(transition)) return invalid(locale, { transition: "invalid" });
    const reasonCode = str(fd, "reason_code");
    const reason = str(fd, "reason").slice(0, 500);
    if (transition === "decline" && !reasonCode) return invalid(locale, { reason_code: t("booking.errReason") });
    const body: AppointmentTransitionRequest = { transition };
    if (reasonCode && (REASONS as readonly string[]).includes(reasonCode)) body.reason_code = reasonCode as AppointmentTransitionRequest["reason_code"];
    if (reason) body.reason = reason;
    if (transition === "no_show") body.party = "customer";
    const api = await userApi();
    // Optimistic concurrency: act on the version the user saw.
    const etag = str(fd, "etag");
    await unwrap(
      api.appointment.POST("/appointments/{id}/status", {
        params: { path: { id }, header: { ...idempotencyHeader(str(fd, "idempotency_key") || undefined), ...(etag ? { "If-Match": etag } : {}) } },
        body,
      }),
    );
    revalidatePath(`/${locale}`, "layout");
    return t(`booking.done_${transition}`);
  }, (locale) => ({ conflict: getT(locale)("booking.stale") }));
}

export async function rescheduleAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const slot = str(fd, "slot");
    if (!ISO.test(slot)) return invalid(locale, { slot: t("booking.errSlot") });
    const api = await userApi();
    const etag = str(fd, "etag");
    const next = await unwrap(
      api.appointment.POST("/appointments/{id}/reschedule", {
        params: { path: { id: str(fd, "appointment_id") }, header: { ...idempotencyHeader(str(fd, "idempotency_key") || undefined), ...(etag ? { "If-Match": etag } : {}) } },
        body: { scheduled_at: slot, ...(str(fd, "reason") ? { reason: str(fd, "reason").slice(0, 500) } : {}) },
      }),
    );
    target = `/${locale}/account/bookings/${next.id}?rescheduled=1`;
  }, (locale) => ({ conflict: getT(locale)("booking.slotTaken") }));
  if (state.ok && target) redirect(target);
  return state;
}

/** Quote (server-side pricing) + payment intent for an appointment; the customer then confirms with the processor. */
export async function startPaymentAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    const subjectType = str(fd, "subject_type") === "concierge_case" ? "concierge_case" : "appointment";
    const quoteId =
      str(fd, "quote_id") ||
      (await unwrap(api.payment.POST("/payment-quotes", { body: { subject_type: subjectType, subject_id: str(fd, "subject_id") } }))).id;
    const payment = await unwrap(
      api.payment.POST("/payments", { params: { header: idempotencyHeader(str(fd, "payment_key") || undefined) }, body: { quote_id: quoteId } }),
    );
    target = `/${locale}/account/payments/${payment.id}`;
  });
  if (state.ok && target) redirect(target);
  return state;
}

export async function refreshPaymentAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    await unwrapResponse(api.payment.POST("/payments/{id}/refresh", { params: { path: { id: str(fd, "payment_id") } } }));
    revalidatePath(`/${locale}/account/payments`, "layout");
    return getT(locale)("payments.refreshed");
  });
}
