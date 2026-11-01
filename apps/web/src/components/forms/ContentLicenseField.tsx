import type { Locale } from "@healuxa/i18n";
import Link from "next/link";

import { CheckboxField } from "@/components/forms/fields";

import { getT } from "@/lib/i18n";

/**
 * Content Rights consent on profile submission. The server action rejects the form unless it is
 * ticked, and provider-service records the accepted licence version (accept_content_license: true).
 */
export function ContentLicenseField({ locale }: { locale: Locale }) {
  const t = getT(locale);
  return (
    <div className="mt-6">
      <CheckboxField name="accept_content_license" label={t("legal.contentLicense.accept")} required />
      <p className="ms-8 mt-1 text-sm text-text-muted">
        {t("legal.contentLicense.hint")}{" "}
        <Link href={`/${locale}/legal/content-rights`} className="underline" target="_blank">
          {t("legal.contentLicense.link")}
        </Link>
      </p>
    </div>
  );
}
