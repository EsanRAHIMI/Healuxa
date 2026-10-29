import { headers } from "next/headers";

import { ButtonLink } from "@/components/ui/primitives";
import { getT, isLaunchLocale } from "@/lib/i18n";

export default async function NotFound() {
  const raw = (await headers()).get("x-hx-locale") ?? "en";
  const locale = isLaunchLocale(raw) ? raw : "en";
  const t = getT(locale);
  return (
    <div className="hx-container py-20 text-center">
      <p className="text-sm font-medium tracking-wide text-accent uppercase">404</p>
      <h1 className="mt-2 text-4xl">{t("errors.notFoundTitle")}</h1>
      <p className="mx-auto mt-3 max-w-prose text-text-muted">{t("errors.notFoundBody")}</p>
      <div className="mt-8 flex justify-center">
        <ButtonLink href={`/${locale}`}>{t("errors.goHome")}</ButtonLink>
      </div>
    </div>
  );
}
