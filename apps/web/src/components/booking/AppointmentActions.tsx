import { newIdempotencyKey, type Appointment } from "@healuxa/api-client";
import type { Locale } from "@healuxa/i18n";

import { transitionAppointmentAction } from "@/actions/booking";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SelectField, SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { getT } from "@/lib/i18n";

/**
 * Lifecycle buttons for one appointment. `side` decides which transitions are offered; the
 * appointment-service state machine is the authority and rejects anything not allowed.
 */
export function AppointmentActions({ appointment, side, locale }: { appointment: Appointment; side: "customer" | "practice"; locale: Locale }) {
  const t = getT(locale);
  const hidden = { appointment_id: appointment.id, etag: `"v${appointment.version}"`, idempotency_key: newIdempotencyKey("appt") };
  const s = appointment.status;
  const cancel = (
    <ConfirmButton
      trigger={t("booking.cancel")}
      title={t("booking.cancelTitle")}
      description={t("booking.cancelBody")}
      confirmLabel={t("booking.cancel")}
      cancelLabel={t("common.back")}
      name="transition"
      value="cancel"
      testId="cancel-appointment"
    />
  );
  const cancelReason = side === "customer" ? "customer_request" : "provider_unavailable";
  if (side === "customer") {
    if (!["held", "requested", "confirmed"].includes(s)) return null;
    return (
      <Form action={transitionAppointmentAction} locale={locale} hidden={{ ...hidden, reason_code: cancelReason }} label={t("booking.actions")}>
        <div className="flex flex-wrap gap-2">
          {s === "held" ? (
            <SubmitButton name="transition" value="submit" pendingLabel={t("common.saving")} testId="submit-request">
              {t("booking.submitRequest")}
            </SubmitButton>
          ) : null}
          {cancel}
        </div>
      </Form>
    );
  }
  if (s === "requested") {
    return (
      <div className="flex flex-wrap items-end gap-4">
        <Form action={transitionAppointmentAction} locale={locale} hidden={hidden} label={t("booking.accept")}>
          <SubmitButton name="transition" value="accept" pendingLabel={t("common.saving")} testId="accept-appointment">
            {t("booking.accept")}
          </SubmitButton>
        </Form>
        <Form action={transitionAppointmentAction} locale={locale} hidden={hidden} label={t("booking.decline")}>
          <div className="flex flex-wrap items-end gap-2">
            <SelectField
              name="reason_code"
              label={t("booking.declineReason")}
              options={(["no_capacity", "out_of_scope", "schedule_conflict", "other"] as const).map((r) => ({ value: r, label: t(`booking.reason_${r}`) }))}
            />
            <SubmitButton name="transition" value="decline" variant="secondary" pendingLabel={t("common.saving")}>
              {t("booking.decline")}
            </SubmitButton>
          </div>
        </Form>
      </div>
    );
  }
  if (s === "confirmed" || s === "checked_in") {
    return (
      <Form action={transitionAppointmentAction} locale={locale} hidden={{ ...hidden, reason_code: cancelReason }} label={t("booking.actions")}>
        <div className="flex flex-wrap gap-2">
          {s === "confirmed" ? (
            <SubmitButton name="transition" value="check_in" variant="secondary" pendingLabel={t("common.saving")}>
              {t("booking.checkIn")}
            </SubmitButton>
          ) : null}
          <SubmitButton name="transition" value="complete" variant="secondary" pendingLabel={t("common.saving")}>
            {t("booking.complete")}
          </SubmitButton>
          {s === "confirmed" ? (
            <SubmitButton name="transition" value="no_show" variant="ghost" pendingLabel={t("common.saving")}>
              {t("booking.noShow")}
            </SubmitButton>
          ) : null}
          {s === "confirmed" ? cancel : null}
        </div>
      </Form>
    );
  }
  return null;
}
