import { newIdempotencyKey, unwrap } from "@healuxa/api-client";
import { formatDate, formatWallTime, timeZoneLabel, type Locale } from "@healuxa/i18n";
import Link from "next/link";

import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { EmptyState, buttonClass } from "@/components/ui/primitives";
import { anonymousApi } from "@/lib/api";
import type { FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

const DAYS = 7;

function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/**
 * Week view of bookable slots from appointment-service (derived from provider availability, opening
 * hours, exceptions and existing holds). Times are shown in the BRANCH time zone with the zone named.
 * Selecting a slot submits `action` with `slot` = UTC start.
 */
export async function SlotPicker({
  serviceId,
  locale,
  from,
  basePath,
  action,
  hidden,
  submitLabel,
}: {
  serviceId: string;
  locale: Locale;
  from: string;
  basePath: string;
  action: (prev: FormState, fd: FormData) => Promise<FormState>;
  hidden: Record<string, string>;
  submitLabel: string;
}) {
  const t = getT(locale);
  const today = new Date().toISOString().slice(0, 10);
  const start = from < today ? today : from;
  const to = addDays(start, DAYS - 1);
  const sep = basePath.includes("?") ? "&" : "?";
  const api = await anonymousApi();
  const res = await settle(() => unwrap(api.appointment.GET("/services/{service_id}/slots", { params: { path: { service_id: serviceId }, query: { from: start, to } } })));
  const nav = (
    <nav aria-label={t("booking.weekNav")} className="flex flex-wrap items-center justify-between gap-3">
      {start > today ? (
        <Link href={`${basePath}${sep}from=${addDays(start, -DAYS)}`} className={buttonClass("secondary", "sm")} scroll={false}>
          {t("booking.prevWeek")}
        </Link>
      ) : (
        <span />
      )}
      <p className="text-sm font-medium">
        {formatDate(start, locale)} – {formatDate(to, locale)}
      </p>
      <Link href={`${basePath}${sep}from=${addDays(start, DAYS)}`} className={buttonClass("secondary", "sm")} scroll={false}>
        {t("booking.nextWeek")}
      </Link>
    </nav>
  );
  if (!res.ok) {
    return (
      <div className="space-y-4">
        {nav}
        <ServiceError error={res.error} locale={locale} />
      </div>
    );
  }
  const { slots, timezone } = res.value;
  const byDay = new Map<string, typeof slots>();
  for (const s of slots) {
    const day = s.local_start.slice(0, 10);
    byDay.set(day, [...(byDay.get(day) ?? []), s]);
  }
  return (
    <div className="space-y-4">
      {nav}
      <p className="text-sm text-text-muted">{t("common.timezoneNote", { zone: timezone, offset: timeZoneLabel(timezone, locale) })}</p>
      {slots.length === 0 ? (
        <EmptyState title={t("booking.noSlots")} body={t("booking.noSlotsBody")} />
      ) : (
        <Form action={action} locale={locale} label={t("booking.chooseTime")} hidden={{ ...hidden, idempotency_key: newIdempotencyKey("hold") }} showSuccess={false} testId="slot-form">
          <fieldset>
            <legend className="sr-only">{t("booking.chooseTime")}</legend>
            <div className="space-y-5">
              {[...byDay.entries()].map(([day, list]) => (
                <div key={day}>
                  <p className="mb-2 font-medium">{formatDate(day, locale, { weekday: "long", day: "numeric", month: "long" })}</p>
                  <div className="flex flex-wrap gap-2">
                    {list.map((s) => (
                      <label key={s.scheduled_at} className="relative">
                        <input type="radio" name="slot" value={s.scheduled_at} required className="peer sr-only" data-testid="slot" />
                        <span className="hx-ltr-nums inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border-strong bg-surface px-3 text-sm peer-checked:border-primary peer-checked:bg-primary peer-checked:text-on-primary peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus">
                          {formatWallTime(s.local_start.slice(11, 16), locale)}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </fieldset>
          <div className="mt-6">
            <SubmitButton pendingLabel={t("booking.holding")} testId="hold-slot">
              {submitLabel}
            </SubmitButton>
          </div>
        </Form>
      )}
    </div>
  );
}
