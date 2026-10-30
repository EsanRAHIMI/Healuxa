import { unwrap } from "@healuxa/api-client";
import { LOCALE_INFO } from "@healuxa/i18n";

import { savePreferencesAction } from "@/actions/notifications";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { CheckboxField, SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Card, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { NOTIFICATION_CATEGORIES, NOTIFICATION_CHANNELS } from "@/lib/notify";

export default async function NotificationPreferences({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const res = await settle(() => unwrap(api.notification.GET("/notifications/preferences/{userId}", { params: { path: { userId: session.userId } } })));
  if (!res.ok) return <ServiceError error={res.error} locale={locale} />;
  const p = res.value;
  return (
    <>
      <PageHeader title={t("notifications.preferences")} lead={t("notifications.preferencesLead")} />
      <Card className="max-w-4xl">
        <Form key={p.updated_at ?? "initial"} action={savePreferencesAction} locale={locale} label={t("notifications.preferences")} testId="notification-preferences">
          <div className="grid gap-5 sm:grid-cols-2">
            <SelectField name="pref_locale" label={t("notifications.language")} defaultValue={p.locale} options={(["en", "ar", "fa"] as const).map((l) => ({ value: l, label: LOCALE_INFO[l].nativeName }))} />
            <TextField name="timezone" label={t("pp.timezone")} defaultValue={p.timezone} required requiredLabel={t("common.required")} dir="ltr" />
            <TextField name="quiet_start" type="time" label={t("notifications.quietStart")} defaultValue={p.quiet_hours?.start ?? ""} optionalLabel={t("common.optional")} />
            <TextField name="quiet_end" type="time" label={t("notifications.quietEnd")} defaultValue={p.quiet_hours?.end ?? ""} optionalLabel={t("common.optional")} />
          </div>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <caption className="mb-2 text-start font-medium">{t("notifications.channelsCaption")}</caption>
              <thead>
                <tr>
                  <th scope="col" className="py-2 text-start">{t("notifications.category")}</th>
                  {NOTIFICATION_CHANNELS.map((ch) => (
                    <th key={ch} scope="col" className="py-2 text-center">{t(`notifications.channel_${ch}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {NOTIFICATION_CATEGORIES.map((cat) => (
                  <tr key={cat} className="border-t border-border">
                    <th scope="row" className="py-2 text-start font-normal">{t(`notifications.category_${cat}`)}</th>
                    {NOTIFICATION_CHANNELS.map((ch) => (
                      <td key={ch} className="py-2 text-center">
                        <input
                          type="checkbox"
                          name={`${cat}.${ch}`}
                          defaultChecked={!!p.channels[cat]?.[ch]}
                          aria-label={`${t(`notifications.category_${cat}`)} — ${t(`notifications.channel_${ch}`)}`}
                          className="size-5 accent-[var(--hx-color-primary)]"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CheckboxField className="mt-6" name="marketing_opt_in" label={t("consent.marketingEmail")} hint={t("notifications.marketingHint")} defaultChecked={p.marketing_opt_in} />
          <div className="mt-6">
            <SubmitButton pendingLabel={t("common.saving")}>{t("common.save")}</SubmitButton>
          </div>
        </Form>
      </Card>
    </>
  );
}
