import { newIdempotencyKey } from "@healuxa/api-client";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { registerAction } from "@/actions/session";
import { CheckboxField, SubmitButton, TextField } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Card } from "@/components/ui/primitives";
import { getSession, safeNext } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";
import { pageMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return pageMetadata(locale, "/register", { title: getT(locale)("auth.signUp"), noindex: true });
}

export default async function RegisterPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const next = safeNext(qp(await searchParams, "next", 512), locale, "");
  if (await getSession()) redirect(next || `/${locale}/account`);
  return (
    <div className="hx-container flex justify-center py-12">
      <Card className="w-full max-w-md">
        <h1 className="text-3xl">{t("auth.signUpTitle")}</h1>
        <p className="mt-2 text-text-muted">{t("auth.signUpLead")}</p>
        <Form
          action={registerAction}
          locale={locale}
          className="mt-6 space-y-5"
          label={t("auth.signUp")}
          showSuccess={false}
          hidden={{ next, idempotency_key: newIdempotencyKey("reg") }}
          testId="register-form"
        >
          <TextField name="identifier" label={t("auth.email")} required requiredLabel={t("common.required")} autoComplete="username" inputMode="email" />
          <TextField name="password" type="password" label={t("auth.password")} hint={t("auth.passwordHint")} required requiredLabel={t("common.required")} autoComplete="new-password" minLength={8} />
          <CheckboxField
            name="terms"
            label={
              <>
                {t("consent.termsAgreement")} (<Link href={`/${locale}/legal/terms`}>{t("nav.terms")}</Link>, <Link href={`/${locale}/legal/privacy`}>{t("nav.privacy")}</Link>)
              </>
            }
          />
          <SubmitButton pendingLabel={t("auth.creatingAccount")} className="w-full">
            {t("auth.signUp")}
          </SubmitButton>
        </Form>
        <p className="mt-6 text-sm text-text-muted">
          {t("auth.haveAccount")} <Link href={`/${locale}/login${next ? `?next=${encodeURIComponent(next)}` : ""}`}>{t("auth.signIn")}</Link>
        </p>
      </Card>
    </div>
  );
}
