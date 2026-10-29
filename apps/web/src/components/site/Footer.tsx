import type { Locale } from "@healuxa/i18n";
import Link from "next/link";

import { setThemeAction } from "@/actions/session";
import { Form } from "@/components/forms/Form";
import { buttonClass } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

export function Footer({ locale, theme }: { locale: Locale; theme: "light" | "dark" | "system" }) {
  const t = getT(locale);
  const groups = [
    {
      title: t("footer.explore"),
      links: [
        { href: `/${locale}/services`, label: t("nav.services") },
        { href: `/${locale}/providers`, label: t("nav.providers") },
        { href: `/${locale}/facilities`, label: t("nav.facilities") },
      ],
    },
    {
      title: t("footer.company"),
      links: [
        { href: `/${locale}/how-it-works`, label: t("nav.howItWorks") },
        { href: `/${locale}/medical-travel`, label: t("nav.medicalTravel") },
        { href: `/${locale}/faq`, label: t("nav.faq") },
        { href: `/${locale}/contact`, label: t("nav.contact") },
      ],
    },
    {
      title: t("footer.partners"),
      links: [
        { href: `/${locale}/provider`, label: t("nav.forProviders") },
        { href: `/${locale}/facility`, label: t("nav.forFacilities") },
      ],
    },
    {
      title: t("footer.legal"),
      links: [
        { href: `/${locale}/legal/privacy`, label: t("nav.privacy") },
        { href: `/${locale}/legal/terms`, label: t("nav.terms") },
        { href: `/${locale}/legal/cookies`, label: t("nav.cookies") },
      ],
    },
  ];
  return (
    <footer className="mt-16 border-t border-border bg-surface-muted">
      <div className="hx-container py-10">
        <nav aria-label={t("a11y.footerNav")} className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {groups.map((g) => (
            <div key={g.title}>
              <h2 className="font-sans text-sm font-semibold">{g.title}</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {g.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-text-muted hover:text-text">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="mt-10 space-y-2 border-t border-border pt-6 text-sm text-text-muted">
          <p>{t("legal.notMedicalAdvice")}</p>
          <p className="font-medium text-text">{t("legal.emergency")}</p>
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm text-text-muted">
          <p>{t("footer.copyright", { year: new Date().getUTCFullYear() })}</p>
          <Form action={setThemeAction} locale={locale} showSuccess={false} label={t("common.theme")}>
            <fieldset className="flex items-center gap-1">
              <legend className="sr-only">{t("common.theme")}</legend>
              {(["system", "light", "dark"] as const).map((v) => (
                <button
                  key={v}
                  type="submit"
                  name="theme"
                  value={v}
                  aria-pressed={theme === v}
                  className={buttonClass(theme === v ? "secondary" : "ghost", "sm")}
                >
                  {t(`common.theme${v[0]!.toUpperCase()}${v.slice(1)}`)}
                </button>
              ))}
            </fieldset>
          </Form>
        </div>
      </div>
    </footer>
  );
}
