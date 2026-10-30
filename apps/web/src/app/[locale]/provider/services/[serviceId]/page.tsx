import { NotFoundError, unwrap } from "@healuxa/api-client";
import Link from "next/link";
import { notFound } from "next/navigation";

import { updateOfferingAction } from "@/actions/provider";
import { FeeBreakdown } from "@/components/domain/FeeBreakdown";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { OfferingFields } from "@/components/portal/OfferingFields";
import { Card, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";

/** Edit one offering (used by the provider portal and, via ?facility=, the facility portal). */
export default async function EditOffering({ params, searchParams }: { params: Promise<{ locale: string; serviceId: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const { serviceId } = await params;
  const facility = (await searchParams).facility;
  const t = getT(locale);
  const api = await userApi();
  const offering = await unwrap(api.provider.GET("/services/{service_id}", { params: { path: { service_id: serviceId } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const back = facility && /^[A-Za-z0-9-]{10,36}$/.test(facility) ? `/${locale}/facility/${facility}/offerings` : `/${locale}/provider/services`;
  return (
    <>
      <PageHeader title={offering.name} lead={t("pp.editOfferingLead")} actions={<Link href={back}>{t("common.back")}</Link>} />
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <Form key={JSON.stringify(offering)} action={updateOfferingAction} locale={locale} label={t("common.edit")} hidden={{ service_id: offering.id }} testId="offering-edit-form">
            <OfferingFields locale={locale} offering={offering} />
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("common.save")}</SubmitButton>
            </div>
          </Form>
        </Card>
        <Card className="h-fit">
          <h2 className="text-lg">{t("pp.currentPrice")}</h2>
          <div className="mt-3">
            <FeeBreakdown offering={offering} locale={locale} />
          </div>
        </Card>
      </div>
    </>
  );
}
