import type { ServiceOffering } from "@healuxa/api-client";
import type { Locale } from "@healuxa/i18n";

import { SelectField, TextArea, TextField } from "@/components/forms/fields";
import { fromMinorUnits } from "@/lib/forms";
import { getT } from "@/lib/i18n";

/** Offering form. Fees are entered in AED (major units) and sent as integer fils. */
export function OfferingFields({ locale, branches, offering }: { locale: Locale; branches?: { value: string; label: string }[]; offering?: ServiceOffering }) {
  const t = getT(locale);
  const req = { required: true, requiredLabel: t("common.required") };
  const opt = { optionalLabel: t("common.optional") };
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {branches ? <SelectField className="sm:col-span-2" name="branch_id" label={t("pp.branch")} {...req} placeholder={t("pp.chooseBranch")} options={branches} /> : null}
      {!offering ? <TextField name="category" label={t("pp.category")} hint={t("pp.categoryHint")} {...req} maxLength={80} /> : null}
      <TextField name="name" label={t("pp.offeringName")} {...req} maxLength={200} defaultValue={offering?.name} />
      {!offering ? <TextArea className="sm:col-span-2" name="description" label={t("pp.offeringDescription")} {...opt} maxLength={4000} /> : null}
      <TextField name="duration_minutes" type="number" label={t("pp.duration")} {...req} min={5} max={720} step={5} defaultValue={String(offering?.duration_minutes ?? 30)} inputMode="numeric" />
      <TextField name="buffer_minutes" type="number" label={t("pp.buffer")} hint={t("pp.bufferHint")} {...opt} min={0} max={240} step={5} defaultValue={String(offering?.buffer_minutes ?? 0)} inputMode="numeric" />
      {!offering ? (
        <SelectField
          name="mode"
          label={t("pp.mode")}
          options={[
            { value: "in_person", label: t("enums.offeringMode.in_person") },
            { value: "home_visit", label: t("enums.offeringMode.home_visit") },
          ]}
        />
      ) : null}
      <SelectField
        name="price_type"
        label={t("pp.priceType")}
        {...req}
        defaultValue={offering?.price_type ?? "fixed"}
        options={(["fixed", "from", "on_request"] as const).map((v) => ({ value: v, label: t(`enums.priceType.${v}`) }))}
      />
      <TextField
        name="professional_fee"
        label={t("pp.professionalFeeAed")}
        hint={t("pp.feeHint")}
        inputMode="decimal"
        defaultValue={fromMinorUnits(offering?.professional_fee?.amount_minor)}
        dir="ltr"
      />
      <TextField name="facility_fee" label={t("pp.facilityFeeAed")} hint={t("pp.facilityFeeHint")} inputMode="decimal" defaultValue={fromMinorUnits(offering?.facility_fee?.amount_minor)} dir="ltr" />
      {offering ? (
        <SelectField
          name="status"
          label={t("common.status")}
          {...req}
          defaultValue={offering.status}
          options={(["draft", "active", "retired"] as const).map((v) => ({ value: v, label: t(`enums.offeringStatus.${v}`) }))}
        />
      ) : null}
      <p className="text-sm text-text-muted sm:col-span-2">{t("payment.feeBreakdownExplainer")}</p>
    </div>
  );
}
