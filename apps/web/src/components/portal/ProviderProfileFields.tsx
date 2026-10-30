import type { Provider } from "@healuxa/api-client";
import { languageName, type Locale } from "@healuxa/i18n";

import { SelectField, TextArea, TextField } from "@/components/forms/fields";
import { getT } from "@/lib/i18n";
import { LANGUAGE_CODES, PROVIDER_TYPES } from "@/lib/query";

export function ProviderProfileFields({ locale, provider, withType }: { locale: Locale; provider?: Provider; withType?: boolean }) {
  const t = getT(locale);
  const req = { required: true, requiredLabel: t("common.required") };
  const opt = { optionalLabel: t("common.optional") };
  return (
    <div className="space-y-5">
      {withType ? (
        <SelectField name="type" label={t("pp.type")} {...req} options={PROVIDER_TYPES.map((v) => ({ value: v, label: t(`enums.providerType.${v}`) }))} defaultValue="doctor" />
      ) : null}
      <TextField name="display_name" label={t("pp.displayName")} hint={t("pp.displayNameHint")} {...req} defaultValue={provider?.display_name} maxLength={160} autoComplete="name" />
      <TextField name="title" label={t("pp.professionalTitle")} hint={t("pp.titleHint")} {...opt} defaultValue={provider?.title ?? ""} maxLength={160} />
      <TextField name="specialties" label={t("pp.specialties")} hint={t("pp.specialtiesHint")} {...req} defaultValue={provider?.specialties.join(", ")} />
      <fieldset>
        <legend className="mb-1.5 block text-sm font-medium">
          {t("pp.languages")} <span className="text-danger" aria-hidden="true">*</span>
        </legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {LANGUAGE_CODES.map((c) => (
            <label key={c} className="flex min-h-11 items-center gap-2 rounded-md border border-border px-3">
              <input type="checkbox" name="languages" value={c} defaultChecked={provider ? provider.languages.includes(c) : c === "en"} className="size-5 accent-[var(--hx-color-primary)]" />
              <span lang={c}>{languageName(c, c === "en" || c === "ar" || c === "fa" || c === "fr" || c === "de" ? c : locale)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-4">
        <legend className="text-sm font-medium">{t("pp.bio")}</legend>
        <p className="text-sm text-text-muted">{t("pp.bioHint")}</p>
        <TextArea name="bio_en" label={t("pp.bioIn", { language: languageName("en", locale) })} {...opt} defaultValue={provider?.bio?.en ?? ""} lang="en" dir="ltr" maxLength={4000} />
        <TextArea name="bio_ar" label={t("pp.bioIn", { language: languageName("ar", locale) })} {...opt} defaultValue={provider?.bio?.ar ?? ""} lang="ar" dir="rtl" maxLength={4000} />
        <TextArea name="bio_fa" label={t("pp.bioIn", { language: languageName("fa", locale) })} {...opt} defaultValue={provider?.bio?.fa ?? ""} lang="fa" dir="rtl" maxLength={4000} />
      </fieldset>
    </div>
  );
}
