import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { loginAction } from "@/actions/session";
import { SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Card } from "@/components/ui/primitives";
import { getSession, safeNext } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return pageMetadata(locale, "/login", { title: getT(locale)("auth.signIn"), noindex: true });
}

export default async function LoginPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const next = safeNext(qp(await searchParams, "next", 512), locale, "");
  if (await getSession()) redirect(next || `/${locale}/account`);
  return (
    <div className="hx-container flex justify-center py-12">
      <Card className="w-full max-w-md">
        <h1 className="text-3xl">{t("auth.signInTitle")}</h1>
        <p className="mt-2 text-text-muted">{t("auth.signInLead")}</p>
        <Form action={loginAction} locale={locale} className="mt-6 space-y-5" label={t("auth.signIn")} showSuccess={false} hidden={{ next }} testId="login-form">
          <TextField name="identifier" label={t("auth.email")} required requiredLabel={t("common.required")} autoComplete="username" inputMode="email" />
          <TextField name="password" type="password" label={t("auth.password")} required requiredLabel={t("common.required")} autoComplete="current-password" />
          <SubmitButton pendingLabel={t("auth.signingIn")} className="w-full">
            {t("auth.signIn")}
          </SubmitButton>
        </Form>
        <p className="mt-6 text-sm text-text-muted">
          {t("auth.noAccount")} <Link href={`/${locale}/register${next ? `?next=${encodeURIComponent(next)}` : ""}`}>{t("auth.signUp")}</Link>
        </p>
      </Card>
    </div>
  );
}
