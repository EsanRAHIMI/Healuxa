import { NotFoundError, unwrap } from "@healuxa/api-client";
import { formatDate, formatDateTime, formatList, languageName } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { selectOptionAction, transitionCaseAction } from "@/actions/concierge";
import { StatusBadge } from "@/components/domain/badges";
import { MessageThread } from "@/components/concierge/MessageThread";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Alert, Card, DefinitionList, PageHeader, Section } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { requireSession } from "@/lib/auth/session";
import { getPublicProvider } from "@/lib/catalog";
import { getT, resolveLocale } from "@/lib/i18n";

export default async function CaseDetail({ params, searchParams }: { params: Promise<{ locale: string; id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const { id } = await params;
  await requireSession(locale);
  const t = getT(locale);
  const api = await userApi();
  const c = await unwrap(api.concierge.GET("/concierge/cases/{id}", { params: { path: { id } } })).catch((e) => {
    if (e instanceof NotFoundError) notFound();
    throw e;
  });
  const options = await unwrap(api.concierge.GET("/concierge/cases/{id}/options", { params: { path: { id } } })).then((r) => r.data).catch(() => []);
  const providers = new Map((await Promise.all(options.map((o) => getPublicProvider(o.provider_id).catch(() => null)))).filter((p) => !!p).map((p) => [p!.id, p!]));
  const open = !["completed", "cancelled"].includes(c.status);
  const created = (await searchParams).created === "1";
  return (
    <>
      <PageHeader title={t(`enums.caseCategory.${c.category}`)} lead={t("concierge.caseLead")} actions={<StatusBadge status={c.status} kind="caseStatus" locale={locale} />} />
      {created ? <Alert tone="success" role="status" className="mb-6" title={t("concierge.createdTitle")}>{t("concierge.createdBody", { due: formatDateTime(c.first_response_due_at, locale) })}</Alert> : null}
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-8">
          {options.length ? (
            <Section title={t("concierge.options")} description={t("concierge.optionsLead")} id="options">
              <ul className="space-y-3">
                {options.map((o) => (
                  <Card as="li" key={o.id} className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{o.label ?? providers.get(o.provider_id)?.display_name ?? t("concierge.option")}</p>
                      {providers.get(o.provider_id) ? <Link href={`/${locale}/providers/${o.provider_id}`} className="text-sm">{providers.get(o.provider_id)!.display_name}</Link> : null}
                      {o.service_id ? (
                        <p className="text-sm">
                          <Link href={`/${locale}/book/${o.service_id}`}>{t("booking.book")}</Link>
                        </p>
                      ) : null}
                    </div>
                    {o.status === "proposed" && open && !c.selected_option_id ? (
                      <Form action={selectOptionAction} locale={locale} hidden={{ case_id: c.id, option_id: o.id }} label={t("concierge.choose")}>
                        <SubmitButton pendingLabel={t("common.saving")}>{t("concierge.choose")}</SubmitButton>
                      </Form>
                    ) : (
                      <StatusBadge status={o.status} kind="optionStatus" locale={locale} />
                    )}
                  </Card>
                ))}
              </ul>
            </Section>
          ) : null}
          <Section title={t("concierge.messages")} id="messages">
            <MessageThread caseId={c.id} locale={locale} viewerRole="customer" canPost={open && !!c.coordinator_id} />
          </Section>
        </div>
        <aside className="space-y-6">
          <Card>
            <DefinitionList
              items={[
                { term: t("concierge.submitted"), value: formatDate(c.created_at, locale) },
                ...(c.preferred_start_date ? [{ term: t("concierge.dates"), value: `${formatDate(c.preferred_start_date, locale)}${c.preferred_end_date ? ` – ${formatDate(c.preferred_end_date, locale)}` : ""}` }] : []),
                ...(c.destination_city ? [{ term: t("concierge.city"), value: c.destination_city }] : []),
                ...(c.languages.length ? [{ term: t("concierge.languages"), value: formatList(c.languages.map((l) => languageName(l, locale)), locale) }] : []),
                { term: t("concierge.coordinator"), value: c.coordinator_id ? t("concierge.assignedYes") : t("concierge.assignedNo") },
              ]}
            />
            {c.needs_note ? <p className="mt-4 whitespace-pre-wrap text-sm">{c.needs_note}</p> : null}
          </Card>
          {open ? (
            <Form action={transitionCaseAction} locale={locale} hidden={{ case_id: c.id, reason: "customer_cancelled" }} label={t("concierge.cancel")}>
              <ConfirmButton trigger={t("concierge.cancel")} title={t("concierge.cancelTitle")} confirmLabel={t("concierge.cancel")} cancelLabel={t("common.back")} name="to_status" value="cancelled" />
            </Form>
          ) : null}
        </aside>
      </div>
    </>
  );
}
