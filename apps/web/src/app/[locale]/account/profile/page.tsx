import { NotFoundError, unwrapResponse, type Profile } from "@healuxa/api-client";

import { saveConsentAction } from "@/actions/account";
import { CheckboxField, SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { CONSENT_KEYS, CONSENT_LABEL_KEYS } from "@/lib/consent";
import { getT, resolveLocale } from "@/lib/i18n";

export default async function ProfilePage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const loaded = await settle(async (): Promise<{ profile: Profile | null; etag: string | null }> => {
    try {
      const res = await unwrapResponse(api.profile.GET("/profiles/{userId}", { params: { path: { userId: session.userId } } }));
      return { profile: res.data, etag: res.etag };
    } catch (error) {
      if (error instanceof NotFoundError) return { profile: null, etag: null };
      throw error;
    }
  });
  const consent = (loaded.ok ? (loaded.value.profile?.consent ?? {}) : {}) as Record<string, { granted?: boolean } | undefined>;
  return (
    <>
      <PageHeader title={t("account.privacyPrefs")} lead={t("account.privacyLead")} />
      <Alert tone="warning" role="note" className="mb-6 max-w-2xl" title={t("legal.reviewNotice")} />
      {!loaded.ok ? (
        <ServiceError error={loaded.error} locale={locale} />
      ) : (
        <Card className="max-w-2xl">
          <Form action={saveConsentAction} locale={locale} label={t("account.privacyPrefs")} hidden={{ etag: loaded.value.etag ?? "" }} testId="consent-form">
            <fieldset className="space-y-5">
              <legend className="mb-2 font-semibold">{t("account.communication")}</legend>
              {CONSENT_KEYS.map((k) => (
                <CheckboxField key={k} name={k} label={t(CONSENT_LABEL_KEYS[k])} defaultChecked={consent[k]?.granted === true} />
              ))}
            </fieldset>
            <p className="mt-5 text-sm text-text-muted">{t("account.consentWithdraw")}</p>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("common.save")}</SubmitButton>
            </div>
          </Form>
        </Card>
      )}
    </>
  );
}
