import { unwrap } from "@healuxa/api-client";
import { formatDate } from "@healuxa/i18n";

import { addStaffAction, removeStaffAction } from "@/actions/facility";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Badge, Card, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";

export default async function StaffPage({ params }: { params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  const t = getT(locale);
  const session = await getSession();
  const api = await userApi();
  const staff = await settle(() => unwrap(api.provider.GET("/facilities/{facility_id}/staff", { params: { path: { facility_id: facilityId } } })));
  if (!staff.ok) return <ServiceError error={staff.error} locale={locale} />;
  const admins = staff.value.data.filter((s) => s.role === "facility_admin").length;
  return (
    <>
      <Section title={t("fp.staff")} description={t("fp.staffLead")} id="list">
        <ul className="space-y-3" data-testid="staff">
          {staff.value.data.map((s) => {
            const lastAdmin = s.role === "facility_admin" && admins <= 1;
            return (
              <Card as="li" key={s.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3 md:py-3">
                <div>
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    <span className="hx-ltr-nums break-all">{s.user_id}</span>
                    {s.user_id === session?.userId ? <Badge tone="primary">{t("fp.you")}</Badge> : null}
                  </p>
                  <p className="text-sm text-text-muted">
                    {t(`enums.staffRole.${s.role}`)}
                    {s.created_at ? ` · ${formatDate(s.created_at, locale)}` : ""}
                  </p>
                </div>
                {lastAdmin ? (
                  <p className="max-w-xs text-sm text-text-muted" data-testid="last-admin-guard">
                    {t("fp.lastAdminGuard")}
                  </p>
                ) : (
                  <Form action={removeStaffAction} locale={locale} hidden={{ facility_id: facilityId, user_id: s.user_id }} label={t("common.remove")}>
                    <ConfirmButton trigger={t("common.remove")} title={t("fp.removeStaffTitle")} description={t("fp.removeStaffBody")} confirmLabel={t("common.remove")} cancelLabel={t("common.cancel")} name="confirm" value="1" />
                  </Form>
                )}
              </Card>
            );
          })}
        </ul>
      </Section>
      <Section title={t("fp.addStaff")} id="add">
        <Card className="max-w-3xl">
          <Form action={addStaffAction} locale={locale} label={t("fp.addStaff")} hidden={{ facility_id: facilityId }} resetOnSuccess>
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField name="user_id" label={t("fp.userId")} hint={t("fp.userIdHint")} required requiredLabel={t("common.required")} dir="ltr" />
              <SelectField name="role" label={t("fp.role")} required requiredLabel={t("common.required")} options={(["facility_admin", "scheduler", "billing"] as const).map((r) => ({ value: r, label: t(`enums.staffRole.${r}`) }))} />
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("fp.addStaff")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
