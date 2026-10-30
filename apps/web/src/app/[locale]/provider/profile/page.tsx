import { redirect } from "next/navigation";

import { updateProviderAction } from "@/actions/provider";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { ProviderProfileFields } from "@/components/portal/ProviderProfileFields";
import { Alert, Card, PageHeader } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyProvider } from "@/lib/portal";

export default async function ProviderProfileEdit({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  const { provider, etag } = mine;
  return (
    <>
      <PageHeader title={t("pp.profile")} lead={t("pp.profileLead")} />
      {provider.verification_status === "verified" ? <Alert tone="warning" role="note" className="mb-6 max-w-3xl" title={t("pp.reverifyWarning")} /> : null}
      <Card className="max-w-3xl">
        {/* key forces fresh defaults after each save (new ETag). */}
        <Form key={etag} action={updateProviderAction} locale={locale} label={t("pp.profile")} hidden={{ provider_id: provider.id, etag }} testId="profile-form">
          <ProviderProfileFields locale={locale} provider={provider} />
          <div className="mt-6">
            <SubmitButton pendingLabel={t("common.saving")}>{t("common.save")}</SubmitButton>
          </div>
        </Form>
      </Card>
    </>
  );
}
