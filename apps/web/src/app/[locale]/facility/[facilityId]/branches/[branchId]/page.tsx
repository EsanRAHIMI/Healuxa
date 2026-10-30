import { unwrap } from "@healuxa/api-client";
import { timeZoneLabel, weekdayName } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { replaceHoursAction } from "@/actions/facility";
import { OpeningHoursTable } from "@/components/domain/OpeningHours";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { HoursRow } from "@/components/portal/HoursRow";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { getBranchesAs } from "@/lib/portal";

/** Weekly opening-hours editor (branch-local wall-clock; up to two windows per day). */
export default async function HoursPage({ params }: { params: Promise<{ locale: string; facilityId: string; branchId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId, branchId } = await params;
  const t = getT(locale);
  const branch = (await getBranchesAs(facilityId)).find((b) => b.id === branchId);
  if (!branch) notFound();
  const api = await userApi();
  const hours = await unwrap(api.provider.GET("/branches/{branch_id}/operating-hours", { params: { path: { branch_id: branchId } } }));
  const byDay = new Map<number, { start: string; end: string }[]>();
  for (const w of hours.windows) byDay.set(w.weekday, [...(byDay.get(w.weekday) ?? []), w]);
  return (
    <>
      <PageHeader title={t("fp.hoursFor", { branch: branch.name })} lead={t("common.timezoneNote", { zone: branch.timezone, offset: timeZoneLabel(branch.timezone, locale) })} actions={<Link href={`/${locale}/facility/${facilityId}/branches`}>{t("common.back")}</Link>} />
      <Alert tone="info" role="note" className="mb-6" title={t("fp.hoursExplainer")} />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card>
          <Form key={JSON.stringify(hours.windows)} action={replaceHoursAction} locale={locale} label={t("fp.editHours")} hidden={{ branch_id: branchId }} testId="hours-form">
            <div className="space-y-3">
              {[0, 1, 2, 3, 4, 5, 6].map((d) => {
                const w = byDay.get(d) ?? [];
                return (
                  <HoursRow
                    key={d}
                    day={d}
                    dayLabel={weekdayName(d, locale)}
                    open={w.length > 0}
                    first={w[0] ?? { start: "09:00", end: "18:00" }}
                    second={w[1]}
                    labels={{ open: t("fp.open"), from: t("fp.from"), to: t("fp.to"), split: t("fp.secondWindow") }}
                  />
                );
              })}
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("fp.saveHours")}</SubmitButton>
            </div>
          </Form>
        </Card>
        <Card className="h-fit">
          <h2 className="text-lg">{t("fp.currentHours")}</h2>
          <div className="mt-3">
            <OpeningHoursTable hours={hours} locale={locale} />
          </div>
        </Card>
      </div>
    </>
  );
}
