import type { Appointment } from "@healuxa/api-client";
import { formatDateTime, formatMoney, type Locale } from "@healuxa/i18n";
import Link from "next/link";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/domain/badges";
import { Card } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

/** Compact appointment card; times in the branch zone (appointment.timezone). */
export function AppointmentRow({ appointment: a, locale, href, subtitle, actions }: { appointment: Appointment; locale: Locale; href?: string; subtitle?: ReactNode; actions?: ReactNode }) {
  const t = getT(locale);
  const when = formatDateTime(a.scheduled_at, locale, { dateStyle: "medium", timeStyle: "short", timeZone: a.timezone });
  return (
    <Card as="li" className="flex flex-col gap-3" data-testid="appointment">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{href ? <Link href={href}>{a.service_name ?? t("booking.appointment")}</Link> : (a.service_name ?? t("booking.appointment"))}</p>
          <p className="text-sm text-text-muted">
            <span className="hx-ltr-nums">{when}</span> ({a.timezone}) · {t("services.duration", { minutes: a.duration_minutes })}
            {a.price ? <> · <span className="hx-ltr-nums">{formatMoney(a.price.amount_minor, a.price.currency, locale)}</span></> : null}
          </p>
          {subtitle ? <p className="text-sm text-text-muted">{subtitle}</p> : null}
        </div>
        <StatusBadge status={a.status} kind="appointmentStatus" locale={locale} />
      </div>
      {actions}
    </Card>
  );
}
