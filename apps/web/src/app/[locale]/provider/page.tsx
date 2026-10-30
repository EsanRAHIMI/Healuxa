import { newIdempotencyKey, unwrap } from "@healuxa/api-client";
import Link from "next/link";

import { applyProviderAction } from "@/actions/provider";
import { StatusBadge, VerificationBadge } from "@/components/domain/badges";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { ProviderProfileFields } from "@/components/portal/ProviderProfileFields";
import { Alert, Card, DefinitionList, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyProvider } from "@/lib/portal";

export default async function ProviderHome({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  await requireSession(locale);
  const t = getT(locale);
  const mine = await getMyProvider().catch(() => undefined);
  if (mine === undefined) return null; // layout shows the error

  if (!mine) {
    return (
      <>
        <PageHeader eyebrow={t("nav.forProviders")} title={t("pp.applyTitle")} lead={t("pp.applyLead")} />
        <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
          <Card>
            <Form action={applyProviderAction} locale={locale} label={t("pp.applyTitle")} showSuccess={false} hidden={{ idempotency_key: newIdempotencyKey("prov") }} testId="apply-form">
              <ProviderProfileFields locale={locale} withType />
              <div className="mt-6">
                <SubmitButton pendingLabel={t("pp.submitting")}>{t("pp.submitApplication")}</SubmitButton>
              </div>
            </Form>
          </Card>
          <Card className="h-fit bg-surface-muted shadow-none">
            <h2 className="text-xl">{t("pp.stepsTitle")}</h2>
            <ol className="mt-3 list-decimal space-y-2 ps-5 text-text-muted">
              <li>{t("pp.step1")}</li>
              <li>{t("pp.step2")}</li>
              <li>{t("pp.step3")}</li>
              <li>{t("pp.step4")}</li>
            </ol>
          </Card>
        </div>
      </>
    );
  }

  const { provider } = mine;
  const api = await userApi();
  const [credentials, affiliations] = await Promise.all([
    unwrap(api.provider.GET("/providers/{id}/credentials", { params: { path: { id: provider.id } } })).then((r) => r.data).catch(() => []),
    unwrap(api.provider.GET("/providers/{id}/affiliations", { params: { path: { id: provider.id } } })).then((r) => r.data).catch(() => []),
  ]);
  const checklist = [
    { done: credentials.length > 0, label: t("pp.checkCredential"), href: `/${locale}/provider/credentials` },
    { done: provider.verification_status === "verified", label: t("pp.checkVerified"), href: `/${locale}/provider/credentials` },
    { done: provider.status === "active", label: t("pp.checkActive") },
    { done: affiliations.some((a) => a.status === "active"), label: t("pp.checkAffiliation"), href: `/${locale}/provider/affiliations` },
  ];
  return (
    <>
      <PageHeader title={provider.display_name} lead={provider.title ?? undefined} />
      {provider.status === "active" && provider.verification_status === "verified" ? (
        <Alert tone="success" role="status" className="mb-6" title={t("pp.liveTitle")}>
          <Link href={`/${locale}/providers/${provider.id}`}>{t("pp.viewPublic")}</Link>
        </Alert>
      ) : (
        <Alert tone="info" role="status" className="mb-6" title={t("pp.notLiveTitle")}>
          {t("pp.notLiveBody")}
        </Alert>
      )}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <h2 className="text-xl">{t("pp.statusTitle")}</h2>
          <DefinitionList
            className="mt-4"
            items={[
              { term: t("pp.verification"), value: <VerificationBadge status={provider.verification_status} locale={locale} /> },
              { term: t("pp.listing"), value: <span data-testid="provider-status"><StatusBadge status={provider.status} kind="providerStatus" locale={locale} /></span> },
              { term: t("common.id"), value: <span className="hx-ltr-nums break-all text-sm">{provider.id}</span> },
            ]}
          />
        </Card>
        <Card>
          <h2 className="text-xl">{t("pp.nextSteps")}</h2>
          <ul className="mt-4 space-y-3">
            {checklist.map((c) => (
              <li key={c.label} className="flex items-start gap-3">
                <span aria-hidden="true" className={c.done ? "text-success" : "text-text-muted"}>
                  {c.done ? "✓" : "○"}
                </span>
                <span>
                  <span className="sr-only">{c.done ? t("pp.done") : t("pp.todo")}: </span>
                  {c.href && !c.done ? <Link href={c.href}>{c.label}</Link> : c.label}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
