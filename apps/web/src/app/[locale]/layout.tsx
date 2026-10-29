import { LOCALE_INFO } from "@healuxa/i18n";
import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { THEME_COOKIE } from "@/lib/auth/tokens";
import { env } from "@/lib/env";
import { fontClasses } from "@/lib/fonts";
import { getT, resolveLocale } from "@/lib/i18n";

import "../globals.css";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  return {
    metadataBase: new URL(env.siteUrl),
    title: { default: t("meta.homeTitle"), template: `%s · ${t("common.appName")}` },
    description: t("meta.defaultDescription"),
    applicationName: t("common.appName"),
    formatDetection: { telephone: false, email: false, address: false },
    icons: { icon: "/icon.svg" },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FAF8F5" },
    { media: "(prefers-color-scheme: dark)", color: "#0E1416" },
  ],
};

export default async function LocaleLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const info = LOCALE_INFO[locale];
  const themeCookie = (await cookies()).get(THEME_COOKIE)?.value;
  const theme = themeCookie === "light" || themeCookie === "dark" ? themeCookie : "system";
  return (
    <html lang={locale} dir={info.dir} data-theme={theme === "system" ? undefined : theme} className={fontClasses(locale)}>
      <body className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only z-50 rounded-md bg-primary px-4 py-2 text-on-primary focus:not-sr-only focus:fixed focus:start-4 focus:top-4"
        >
          {t("a11y.skipToContent")}
        </a>
        <Header locale={locale} />
        <main id="main" tabIndex={-1} className="flex-1 outline-none">
          {children}
        </main>
        <Footer locale={locale} theme={theme} />
      </body>
    </html>
  );
}
