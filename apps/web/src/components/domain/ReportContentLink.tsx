import type { Locale } from "@healuxa/i18n";
import Link from "next/link";

import { env } from "@/lib/env";
import { getT } from "@/lib/i18n";

/**
 * Content Rights: lets rights holders report a published profile (infringement, inaccuracy) and links
 * to the content rights terms. Reports go to the support mailbox with the profile URL pre-filled.
 */
export function ReportContentLink({ locale, url, kind }: { locale: Locale; url: string; kind: "provider" | "facility" }) {
  const t = getT(locale);
  const subject = encodeURIComponent(`Content report (${kind})`);
  const body = encodeURIComponent(`Profile: ${url}\n\nReason:\n`);
  return (
    <p className="mt-10 flex flex-wrap gap-x-4 gap-y-1 text-sm text-text-muted">
      <a href={`mailto:${env.supportEmail}?subject=${subject}&body=${body}`} className="underline">
        {t("legal.contentLicense.report")}
      </a>
      <Link href={`/${locale}/legal/content-rights`} className="underline">
        {t("legal.contentLicense.link")}
      </Link>
    </p>
  );
}
