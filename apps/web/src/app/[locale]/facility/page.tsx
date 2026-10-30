import { newIdempotencyKey } from "@healuxa/api-client";
import Link from "next/link";

import { openFacilityAction, registerFacilityAction } from "@/actions/facility";
import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { FacilityFields } from "@/components/portal/FacilityFields";
import { Card, EmptyState, PageHeader, Section } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyFacilities } from "@/lib/portal";

export default async function FacilityHome({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  // Server-side membership lookup: works on any device, no browser-held state.
  const facilities = await getMyFacilities();
  return (
    <>
      <PageHeader eyebrow={t("nav.forFacilities")} title={t("fp.title")} lead={t("fp.lead")} />
      <Section title={t("fp.myFacilities")} id="mine">
        {facilities.length === 0 ? (
          <EmptyState title={t("fp.noFacilities")} body={t("fp.noFacilitiesBody")} />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {facilities.map((f) => (
              <Card as="li" key={f!.id} className="flex flex-col gap-2">
                <Link href={`/${locale}/facility/${f!.id}`} className="text-xl text-text">
                  {f!.name}
                </Link>
                <div className="flex flex-wrap gap-2">
                  <VerificationBadge status={f!.verification_status} locale={locale} />
                  <StatusBadge status={f!.status} kind="providerStatus" locale={locale} />
                </div>
              </Card>
            ))}
          </ul>
        )}
        <Card className="mt-6 max-w-xl">
          <Form action={openFacilityAction} locale={locale} label={t("fp.openById")} showSuccess={false}>
            <TextField name="facility_id" label={t("fp.openById")} hint={t("fp.openByIdHint")} required requiredLabel={t("common.required")} />
            <div className="mt-4">
              <SubmitButton variant="secondary" pendingLabel={t("common.loading")}>
                {t("common.open")}
              </SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
      <Section title={t("fp.register")} description={t("fp.registerLead")} id="register">
        <Card className="max-w-3xl">
          <Form action={registerFacilityAction} locale={locale} label={t("fp.register")} showSuccess={false} hidden={{ idempotency_key: newIdempotencyKey("fac") }} testId="facility-register-form">
            <FacilityFields locale={locale} withLicence />
            <div className="mt-6">
              <SubmitButton pendingLabel={t("pp.submitting")}>{t("fp.register")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
