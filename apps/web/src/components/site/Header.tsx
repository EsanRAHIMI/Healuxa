import { LAUNCH_LOCALES, LOCALE_INFO, type Locale } from "@healuxa/i18n";
import Link from "next/link";

import { logoutAction } from "@/actions/session";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { buttonClass } from "@/components/ui/primitives";
import { getSession, hasPermission } from "@/lib/auth/session";
import { getT } from "@/lib/i18n";

import { LanguageSwitcher } from "./LanguageSwitcher";

export function Wordmark({ locale }: { locale: Locale }) {
  const t = getT(locale);
  return (
    <Link href={`/${locale}`} className="inline-flex items-baseline gap-2 text-text no-underline" aria-label={t("nav.homeLabel")}>
      <svg viewBox="0 0 24 24" className="size-6 self-center text-primary" aria-hidden="true">
        <path fill="currentColor" d="M12 2.5c.6 0 1 .4 1 1v7.5h7.5c.6 0 1 .4 1 1s-.4 1-1 1H13v7.5c0 .6-.4 1-1 1s-1-.4-1-1V13H3.5c-.6 0-1-.4-1-1s.4-1 1-1H11V3.5c0-.6.4-1 1-1Z" opacity=".25" />
        <circle cx="12" cy="12" r="4.25" fill="none" stroke="currentColor" strokeWidth="1.75" />
      </svg>
      <span className="font-serif text-xl font-medium tracking-tight">{t("common.appName")}</span>
    </Link>
  );
}

export async function Header({ locale }: { locale: Locale }) {
  const t = getT(locale);
  const session = await getSession();
  const isStaff = hasPermission(session, "providers:verify") || hasPermission(session, "facilities:verify");
  const nav = [
    { href: `/${locale}/services`, label: t("nav.services") },
    { href: `/${locale}/providers`, label: t("nav.providers") },
    { href: `/${locale}/facilities`, label: t("nav.facilities") },
    { href: `/${locale}/how-it-works`, label: t("nav.howItWorks") },
    { href: `/${locale}/medical-travel`, label: t("nav.medicalTravel") },
  ];
  return (
    <header className="border-b border-border bg-surface">
      <div className="hx-container flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3">
        <Wordmark locale={locale} />
        <div className="flex flex-wrap items-center gap-2">
          <LanguageSwitcher
            current={locale}
            label={t("a11y.languageSwitcher")}
            options={LAUNCH_LOCALES.map((l) => ({ code: l, nativeName: LOCALE_INFO[l].nativeName, dir: LOCALE_INFO[l].dir }))}
          />
          {session ? (
            <div className="flex items-center gap-2">
              <Link href={`/${locale}/account`} className={buttonClass("ghost", "sm")} data-testid="nav-account">
                {t("nav.account")}
              </Link>
              {isStaff ? (
                <Link href={`/${locale}/admin`} className={buttonClass("ghost", "sm")}>
                  {t("nav.admin")}
                </Link>
              ) : null}
              <Form action={logoutAction} locale={locale} showSuccess={false} className="contents" label={t("auth.signOut")}>
                <SubmitButton variant="secondary" pendingLabel={t("auth.signingOut")} className="min-h-9 px-3 text-sm" testId="sign-out">
                  {t("auth.signOut")}
                </SubmitButton>
              </Form>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link href={`/${locale}/login`} className={buttonClass("ghost", "sm")} data-testid="nav-sign-in">
                {t("auth.signIn")}
              </Link>
              <Link href={`/${locale}/register`} className={buttonClass("primary", "sm")}>
                {t("auth.signUp")}
              </Link>
            </div>
          )}
        </div>
      </div>
      <nav aria-label={t("a11y.mainNav")} className="border-t border-border">
        <ul className="hx-container flex gap-1 overflow-x-auto py-1 text-sm md:gap-3">
          {nav.map((item) => (
            <li key={item.href} className="shrink-0">
              <Link href={item.href} className="inline-flex min-h-10 items-center rounded-md px-2 text-text no-underline hover:bg-surface-muted">
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
