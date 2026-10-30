import type { Facility } from "@healuxa/api-client";
import { languageName, type Locale } from "@healuxa/i18n";

import { SelectField, TextArea, TextField } from "@/components/forms/fields";
import { getT } from "@/lib/i18n";
import { FACILITY_TYPES } from "@/lib/query";

export function FacilityFields({ locale, facility, withLicence }: { locale: Locale; facility?: Facility; withLicence?: boolean }) {
  const t = getT(locale);
  const req = { required: true, requiredLabel: t("common.required") };
  const opt = { optionalLabel: t("common.optional") };
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {withLicence ? <SelectField name="type" label={t("fp.type")} {...req} options={FACILITY_TYPES.map((v) => ({ value: v, label: t(`enums.facilityType.${v}`) }))} /> : null}
      <TextField name="name" label={t("fp.name")} {...req} maxLength={200} defaultValue={facility?.name} />
      {withLicence ? (
        <>
          <TextField name="license_authority" label={t("fp.licenceAuthority")} hint={t("pp.authorityHint")} {...req} maxLength={64} />
          <TextField name="license_number" label={t("fp.licenceNumber")} {...req} maxLength={64} />
        </>
      ) : null}
      <TextField name="website" type="url" label={t("fp.website")} {...opt} maxLength={300} defaultValue={facility?.website ?? ""} dir="ltr" placeholder="https://" />
      <TextField name="phone" type="tel" label={t("fp.phone")} {...opt} maxLength={32} defaultValue={facility?.phone ?? ""} dir="ltr" autoComplete="tel" />
      {(["en", "ar", "fa"] as const).map((l) => (
        <TextArea
          key={l}
          className="sm:col-span-2"
          name={`description_${l}`}
          label={t("fp.descriptionIn", { language: languageName(l, locale) })}
          {...opt}
          lang={l}
          dir={l === "en" ? "ltr" : "rtl"}
          maxLength={4000}
          defaultValue={facility?.description?.[l] ?? ""}
        />
      ))}
    </div>
  );
}
