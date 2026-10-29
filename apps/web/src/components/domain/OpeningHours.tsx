import type { OperatingHours } from "@healuxa/api-client";
import { formatWallTime, timeZoneLabel, weekdayName, type Locale } from "@healuxa/i18n";

import { getT } from "@/lib/i18n";

/** Weekly hours in branch-local time with the zone stated explicitly (never converted to the viewer's zone). */
export function OpeningHoursTable({ hours, locale, caption }: { hours: OperatingHours; locale: Locale; caption?: string }) {
  const t = getT(locale);
  const tz = hours.timezone ?? "Asia/Dubai";
  const byDay = new Map<number, { start: string; end: string }[]>();
  for (const w of hours.windows) byDay.set(w.weekday, [...(byDay.get(w.weekday) ?? []), { start: w.start, end: w.end }]);
  return (
    <table className="w-full text-sm">
      <caption className="mb-2 text-start text-text-muted">
        {caption ?? t("facility.hoursCaption")} · {t("common.timezoneNote", { zone: tz, offset: timeZoneLabel(tz, locale) })}
      </caption>
      <tbody>
        {[0, 1, 2, 3, 4, 5, 6].map((d) => {
          const windows = byDay.get(d) ?? [];
          return (
            <tr key={d} className="border-t border-border">
              <th scope="row" className="py-1.5 pe-4 text-start font-medium">
                {weekdayName(d, locale)}
              </th>
              <td className="py-1.5 text-end">
                {windows.length === 0 ? (
                  <span className="text-text-muted">{t("facility.closed")}</span>
                ) : (
                  windows.map((w, i) => (
                    <span key={i} className="hx-ltr-nums block">
                      {formatWallTime(w.start, locale)} – {formatWallTime(w.end, locale)}
                    </span>
                  ))
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
