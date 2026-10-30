import { notFound } from "next/navigation";

import { updateFacilityAction } from "@/actions/facility";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { FacilityFields } from "@/components/portal/FacilityFields";
import { Alert, Card, DefinitionList, Section } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { getFacilityAs } from "@/lib/portal";

export default async function FacilityOverview({ params, searchParams }: { params: Promise<{ locale: string; facilityId: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  const t = getT(locale);
  const facility = await getFacilityAs(facilityId);
  if (!facility) notFound();
  const registered = (await searchParams).registered === "1";
  return (
    <>
      {registered ? <Alert tone="success" role="status" className="mb-6" title={t("fp.registeredTitle")}>{t("fp.registeredBody")}</Alert> : null}
      {facility.verification_status !== "verified" ? <Alert tone="info" role="note" className="mb-6" title={t("fp.pendingVerification")} /> : null}
      <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
        <Card className="h-fit">
          <DefinitionList
            items={[
              { term: t("common.id"), value: <span className="hx-ltr-nums break-all text-sm" data-testid="facility-id">{facility.id}</span> },
              { term: t("fp.type"), value: t(`enums.facilityType.${facility.type}`) },
              { term: t("fp.licenceAuthority"), value: facility.license_authority ?? "—" },
              { term: t("fp.licenceNumber"), value: <span className="hx-ltr-nums">{facility.license_number ?? "—"}</span> },
            ]}
          />
        </Card>
        <Section title={t("fp.details")} id="edit">
          <Card>
            <Form key={JSON.stringify(facility)} action={updateFacilityAction} locale={locale} label={t("fp.details")} hidden={{ facility_id: facility.id }}>
              <FacilityFields locale={locale} facility={facility} />
              <div className="mt-6">
                <SubmitButton pendingLabel={t("common.saving")}>{t("common.save")}</SubmitButton>
              </div>
            </Form>
          </Card>
        </Section>
      </div>
    </>
  );
}
