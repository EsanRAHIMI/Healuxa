import { regionName } from "@healuxa/i18n";
import Link from "next/link";

import { createBranchAction } from "@/actions/facility";
import { StatusBadge } from "@/components/domain/badges";
import { SelectField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Card, EmptyState, Section } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { getBranchesAs } from "@/lib/portal";

const ZONES = ["Asia/Dubai", "Asia/Riyadh", "Asia/Qatar", "Asia/Bahrain", "Asia/Muscat", "Asia/Kuwait", "Asia/Tehran", "Europe/London", "Europe/Paris", "Europe/Berlin"];

export default async function BranchesPage({ params }: { params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  const t = getT(locale);
  const branches = await getBranchesAs(facilityId);
  const req = { required: true, requiredLabel: t("common.required") };
  const opt = { optionalLabel: t("common.optional") };
  return (
    <>
      <Section title={t("fp.branches")} id="list">
        {branches.length === 0 ? (
          <EmptyState title={t("facility.noBranches")} body={t("fp.noBranchesBody")} />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2" data-testid="branches">
            {branches.map((b) => (
              <Card as="li" key={b.id} className="flex flex-col gap-2">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-xl">{b.name}</h3>
                  <StatusBadge status={b.status ?? "active"} kind="branchStatus" locale={locale} />
                </div>
                <p className="text-sm text-text-muted">
                  {b.address_line}, {b.city}, {regionName(b.country, locale)} · {b.timezone}
                </p>
                <p className="text-xs text-text-muted hx-ltr-nums">{b.id}</p>
                <Link href={`/${locale}/facility/${facilityId}/branches/${b.id}`} className="mt-auto" data-testid="edit-hours">
                  {t("fp.editHours")}
                </Link>
              </Card>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("fp.addBranch")} id="add">
        <Card className="max-w-3xl">
          <Form action={createBranchAction} locale={locale} label={t("fp.addBranch")} hidden={{ facility_id: facilityId }} resetOnSuccess testId="branch-form">
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField name="name" label={t("fp.branchName")} {...req} maxLength={200} />
              <TextField name="address_line" label={t("fp.address")} {...req} maxLength={300} autoComplete="street-address" />
              <TextField name="city" label={t("providers.city")} {...req} maxLength={100} autoComplete="address-level2" />
              <TextField name="emirate" label={t("fp.emirate")} {...opt} maxLength={64} />
              <TextField name="country" label={t("fp.country")} hint={t("fp.countryHint")} {...req} defaultValue="AE" maxLength={2} dir="ltr" />
              <SelectField name="timezone" label={t("pp.timezone")} {...req} defaultValue="Asia/Dubai" options={ZONES.map((z) => ({ value: z, label: z }))} />
              <TextField name="latitude" label={t("fp.latitude")} {...opt} inputMode="decimal" dir="ltr" />
              <TextField name="longitude" label={t("fp.longitude")} {...opt} inputMode="decimal" dir="ltr" />
              <TextField name="phone" type="tel" label={t("fp.phone")} {...opt} dir="ltr" />
            </div>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("common.saving")}>{t("fp.addBranch")}</SubmitButton>
            </div>
          </Form>
        </Card>
      </Section>
    </>
  );
}
