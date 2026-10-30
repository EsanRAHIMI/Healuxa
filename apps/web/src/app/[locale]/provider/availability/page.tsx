import { unwrap } from "@healuxa/api-client";
import { formatDate, formatDateTime, formatWallTime, timeZoneLabel, weekdayName } from "@healuxa/i18n";
import { redirect } from "next/navigation";

import { createExceptionAction, createRuleAction, deleteRuleAction } from "@/actions/provider";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Alert, Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { branchLabels, getMyProvider } from "@/lib/portal";

export default async function AvailabilityPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  const { provider } = mine;
  const api = await userApi();
  const today = new Date().toISOString().slice(0, 10);
  const until = new Date(Date.now() + 180 * 86400_000).toISOString().slice(0, 10);
  const data = await settle(async () => {
    const [affs, rules, exceptions] = await Promise.all([
      unwrap(api.provider.GET("/providers/{id}/affiliations", { params: { path: { id: provider.id } } })),
      unwrap(api.provider.GET("/providers/{id}/availability-rules", { params: { path: { id: provider.id } } })),
      unwrap(api.provider.GET("/providers/{id}/availability-exceptions", { params: { path: { id: provider.id }, query: { from: today, to: until } } })),
    ]);
    const active = affs.data.filter((a) => a.status === "active");
    return { active, rules: rules.data, exceptions: exceptions.data, labels: await branchLabels(active.map((a) => a.facility_id)) };
  });
  if (!data.ok) return <ServiceError error={data.error} locale={locale} />;
  const { active, rules, exceptions, labels } = data.value;
  const branchName = (id: string | null | undefined) => {
    if (!id) return t("pp.allBranches");
    const l = labels.get(id);
    return l ? `${l.facility} — ${l.branch.name}` : id;
  };
  const branchOptions = active.map((a) => ({ value: a.branch_id, label: `${branchName(a.branch_id)} (${labels.get(a.branch_id)?.branch.timezone ?? "?"})` }));
  const zones = [...new Set(active.map((a) => labels.get(a.branch_id)?.branch.timezone).filter((z): z is string => !!z))];
  const defaultZone = zones[0] ?? "Asia/Dubai";
  const sorted = [...rules].sort((a, b) => a.branch_id.localeCompare(b.branch_id) || a.weekday - b.weekday || a.start.localeCompare(b.start));
  const req = { required: true, requiredLabel: t("common.required") };

  return (
    <>
      <PageHeader title={t("pp.availability")} lead={t("pp.availabilityLead")} />
      <Alert tone="info" role="note" className="mb-6" title={t("pp.timezoneExplainer")} />
      <Section title={t("pp.weeklyRules")} id="rules">
        {sorted.length === 0 ? (
          <EmptyState title={t("pp.noRules")} />
        ) : (
          <ul className="space-y-2" data-testid="rules">
            {sorted.map((r) => (
              <Card as="li" key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3 md:py-3">
                <div>
                  <p className="font-medium">
                    {weekdayName(r.weekday, locale)} · <span className="hx-ltr-nums">{formatWallTime(r.start, locale)} – {formatWallTime(r.end, locale)}</span>
                  </p>
                  <p className="text-sm text-text-muted">
                    {branchName(r.branch_id)} · {t("common.timezoneNote", { zone: r.timezone ?? defaultZone, offset: timeZoneLabel(r.timezone ?? defaultZone, locale) })}
                    {" · "}
                    {t("pp.effective", { from: formatDate(r.effective_from, locale), until: r.effective_until ? formatDate(r.effective_until, locale) : t("pp.noEnd") })}
                  </p>
                </div>
                <Form action={deleteRuleAction} locale={locale} hidden={{ rule_id: r.id }} label={t("common.delete")}>
                  <ConfirmButton trigger={t("common.delete")} title={t("pp.deleteRuleTitle")} confirmLabel={t("common.delete")} cancelLabel={t("common.cancel")} name="confirm" value="1" />
                </Form>
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("pp.addRule")} id="add-rule">
        {branchOptions.length === 0 ? (
          <Alert tone="info" role="note" title={t("pp.needActiveAffiliation")} />
        ) : (
          <Card className="max-w-3xl">
            <Form action={createRuleAction} locale={locale} label={t("pp.addRule")} hidden={{ provider_id: provider.id }} testId="rule-form">
              <div className="grid gap-5 sm:grid-cols-2">
                <SelectField className="sm:col-span-2" name="branch_id" label={t("pp.branch")} {...req} options={branchOptions} />
                <fieldset className="sm:col-span-2">
                  <legend className="mb-1.5 text-sm font-medium">{t("pp.weekdays")}</legend>
                  <div className="flex flex-wrap gap-2">
                    {[0, 1, 2, 3, 4, 5, 6].map((d) => (
                      <label key={d} className="flex min-h-11 items-center gap-2 rounded-md border border-border px-3">
                        <input type="checkbox" name="weekday" value={d} className="size-5 accent-[var(--hx-color-primary)]" />
                        {weekdayName(d, locale)}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <TextField name="start" type="time" label={t("pp.startLocal")} {...req} defaultValue="09:00" step={300} />
                <TextField name="end" type="time" label={t("pp.endLocal")} {...req} defaultValue="17:00" step={300} />
                <TextField name="effective_from" type="date" label={t("pp.effectiveFrom")} {...req} defaultValue={today} />
                <TextField name="effective_until" type="date" label={t("pp.effectiveUntil")} optionalLabel={t("common.optional")} />
              </div>
              <div className="mt-6">
                <SubmitButton pendingLabel={t("common.saving")}>{t("pp.addRule")}</SubmitButton>
              </div>
            </Form>
          </Card>
        )}
      </Section>
      <Section title={t("pp.exceptions")} description={t("pp.exceptionsLead")} id="exceptions">
        {exceptions.length === 0 ? (
          <EmptyState title={t("pp.noExceptions")} />
        ) : (
          <ul className="space-y-2" data-testid="exceptions">
            {exceptions.map((e) => {
              const tz = (e.branch_id ? labels.get(e.branch_id)?.branch.timezone : undefined) ?? defaultZone;
              return (
                <Card as="li" key={e.id} className="py-3 md:py-3">
                  <p className="font-medium">{t(`enums.exceptionReason.${e.reason}`)} · {branchName(e.branch_id)}</p>
                  <p className="text-sm text-text-muted hx-ltr-nums">
                    {formatDateTime(e.starts_at, locale, { dateStyle: "medium", timeStyle: "short", timeZone: tz })} – {formatDateTime(e.ends_at, locale, { dateStyle: "medium", timeStyle: "short", timeZone: tz })} ({tz})
                  </p>
                </Card>
              );
            })}
          </ul>
        )}
        <Card className="mt-6 max-w-3xl">
          <h3 className="text-lg">{t("pp.addException")}</h3>
          <Form action={createExceptionAction} locale={locale} label={t("pp.addException")} hidden={{ provider_id: provider.id }} resetOnSuccess>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <SelectField name="branch_id" label={t("pp.branch")} options={[{ value: "", label: t("pp.allBranches") }, ...branchOptions]} />
              <SelectField name="timezone" label={t("pp.timezone")} {...req} defaultValue={defaultZone} options={[...new Set([...zones, "Asia/Dubai"])].map((z) => ({ value: z, label: `${z} (${timeZoneLabel(z, locale)})` }))} />
              <TextField name="start_date" type="date" label={t("pp.startDate")} {...req} defaultValue={today} />
              <TextField name="start_time" type="time" label={t("pp.startTime")} optionalLabel={t("common.optional")} />
              <TextField name="end_date" type="date" label={t("pp.endDate")} {...req} defaultValue={today} />
              <TextField name="end_time" type="time" label={t("pp.endTime")} optionalLabel={t("common.optional")} />
              <SelectField name="reason" label={t("pp.reason")} {...req} options={(["leave", "public_holiday", "training", "other"] as const).map((r) => ({ value: r, label: t(`enums.exceptionReason.${r}`) }))} />
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("pp.addException")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
