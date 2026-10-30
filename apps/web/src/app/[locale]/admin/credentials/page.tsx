import { unwrap, type Provider } from "@healuxa/api-client";
import { formatDate, formatDateTime } from "@healuxa/i18n";
import Link from "next/link";

import { reviewCredentialAction } from "@/actions/admin";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { DecisionForm } from "@/components/portal/DecisionForm";
import { CursorPager } from "@/components/ui/filters";
import { Card, DefinitionList, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { qp } from "@/lib/query";

/** FIFO credential review queue (provider-service GET /admin/credentials?status=submitted). */
export default async function CredentialQueue({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const cursor = qp(await searchParams, "cursor", 512);
  const api = await userApi();
  const res = await settle(async () => {
    const page = await unwrap(api.provider.GET("/admin/credentials", { params: { query: { status: "submitted", limit: 20, cursor } } }));
    const providers = new Map<string, Provider>();
    await Promise.all(
      [...new Set(page.data.map((c) => c.provider_id))].map(async (id) => {
        const p = await unwrap(api.provider.GET("/providers/{id}", { params: { path: { id } } })).catch(() => null);
        if (p) providers.set(id, p);
      }),
    );
    return { page, providers };
  });
  return (
    <>
      <PageHeader title={t("admin.credentials")} lead={t("admin.credentialsLead")} />
      {!res.ok ? (
        <ServiceError error={res.error} locale={locale} />
      ) : res.value.page.data.length === 0 ? (
        <EmptyState title={t("admin.queueEmpty")} />
      ) : (
        <ul className="space-y-4" data-testid="credential-queue">
          {res.value.page.data.map((c) => {
            const p = res.value.providers.get(c.provider_id);
            return (
              <Card as="li" key={c.id} className="grid gap-6 lg:grid-cols-[3fr_2fr]" data-testid="queue-credential">
                <div>
                  <p className="text-lg font-medium">
                    <Link href={`/${locale}/admin/providers/${c.provider_id}`}>{p?.display_name ?? c.provider_id}</Link>
                  </p>
                  <DefinitionList
                    className="mt-3"
                    items={[
                      { term: t("pp.kind"), value: t(`enums.credentialKind.${c.kind}`) },
                      { term: t("pp.authority"), value: c.issuing_authority },
                      { term: t("pp.number"), value: <span className="hx-ltr-nums" data-testid="credential-number">{c.number}</span> },
                      ...(c.jurisdiction ? [{ term: t("pp.jurisdiction"), value: c.jurisdiction }] : []),
                      { term: t("pp.validUntil"), value: c.valid_until ? formatDate(c.valid_until, locale) : "—" },
                      { term: t("admin.submittedAt"), value: <span className="hx-ltr-nums">{formatDateTime(c.submitted_at, locale)}</span> },
                    ]}
                  />
                  <p className="mt-3 text-sm text-text-muted">{t("admin.checkRegistry")}</p>
                </div>
                <DecisionForm action={reviewCredentialAction} locale={locale} hidden={{ provider_id: c.provider_id, credential_id: c.id }} testId="credential-decision" />
              </Card>
            );
          })}
        </ul>
      )}
      {res.ok ? (
        <CursorPager basePath={`/${locale}/admin/credentials`} params={{}} nextCursor={res.value.page.page.next_cursor} isFirst={!cursor} nextLabel={t("common.next")} firstLabel={t("common.firstPage")} navLabel={t("a11y.pagination")} />
      ) : null}
    </>
  );
}
