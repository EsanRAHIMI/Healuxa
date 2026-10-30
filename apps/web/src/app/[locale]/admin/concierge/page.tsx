import { unwrap } from "@healuxa/api-client";
import { formatDateTime } from "@healuxa/i18n";
import Link from "next/link";

import { assignCaseAction } from "@/actions/concierge";
import { StatusBadge } from "@/components/domain/badges";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { CursorPager, FilterBar, FilterSelect } from "@/components/ui/filters";
import { Badge, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT, resolveLocale } from "@/lib/i18n";
import { oneOf, qp } from "@/lib/query";

const STATUSES = ["submitted", "triaged", "assigned", "in_progress", "awaiting_customer", "arranged", "completed", "cancelled", "escalated"] as const;
const CATEGORIES = ["medical_travel", "specialist_search", "second_opinion_coordination", "logistics", "other"] as const;
const ASSIGNEE = ["me", "unassigned", "any"] as const;

/** Coordinator queue (concierge-service /concierge/queue): SLA first, claim in one click. */
export default async function ConciergeQueue({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const sp = await searchParams;
  const filters = {
    status: oneOf(qp(sp, "status"), STATUSES),
    category: oneOf(qp(sp, "category"), CATEGORIES),
    assignee: oneOf(qp(sp, "assignee"), ASSIGNEE),
    breached: qp(sp, "breached") === "1" ? "1" : undefined,
  };
  const cursor = qp(sp, "cursor", 512);
  const api = await userApi();
  const res = await settle(() =>
    unwrap(
      api.concierge.GET("/concierge/queue", {
        params: { query: { status: filters.status, category: filters.category, assignee: filters.assignee, ...(filters.breached ? { breached: true } : {}), limit: 25, cursor } },
      }),
    ),
  );
  const base = `/${locale}/admin/concierge`;
  return (
    <>
      <PageHeader title={t("admin.concierge")} lead={t("admin.conciergeLead")} />
      <FilterBar action={base} label={t("common.filter")} submitLabel={t("common.apply")} clearHref={base} clearLabel={t("common.clearFilters")}>
        <FilterSelect name="assignee" label={t("admin.assignee")} defaultValue={filters.assignee} anyLabel={t("admin.any")} options={ASSIGNEE.map((a) => ({ value: a, label: t(`admin.assignee_${a}`) }))} />
        <FilterSelect name="status" label={t("common.status")} defaultValue={filters.status} anyLabel={t("admin.any")} options={STATUSES.map((s) => ({ value: s, label: t(`enums.caseStatus.${s}`) }))} />
        <FilterSelect name="category" label={t("concierge.category")} defaultValue={filters.category} anyLabel={t("admin.any")} options={CATEGORIES.map((c) => ({ value: c, label: t(`enums.caseCategory.${c}`) }))} />
        <FilterSelect name="breached" label={t("admin.sla")} defaultValue={filters.breached} anyLabel={t("admin.any")} options={[{ value: "1", label: t("admin.slaBreached") }]} />
      </FilterBar>
      <div className="mt-6">
        {!res.ok ? (
          <ServiceError error={res.error} locale={locale} />
        ) : res.value.data.length === 0 ? (
          <EmptyState title={t("admin.queueEmpty")} />
        ) : (
          <ul className="space-y-3" data-testid="concierge-queue">
            {res.value.data.map((c) => (
              <Card as="li" key={c.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <Link href={`${base}/${c.id}`} className="font-medium">
                    {t(`enums.caseCategory.${c.category}`)}
                  </Link>
                  <p className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
                    <StatusBadge status={c.status} kind="caseStatus" locale={locale} />
                    {c.sla_breached ? <Badge tone="danger">{t("admin.slaBreached")}</Badge> : null}
                    <span className="hx-ltr-nums">{t("admin.firstResponseDue", { due: formatDateTime(c.first_response_due_at, locale, { dateStyle: "short", timeStyle: "short" }) })}</span>
                  </p>
                </div>
                {!c.coordinator_id ? (
                  <Form action={assignCaseAction} locale={locale} hidden={{ case_id: c.id }} label={t("admin.claim")} showSuccess={false}>
                    <SubmitButton variant="secondary" pendingLabel={t("common.saving")}>{t("admin.claim")}</SubmitButton>
                  </Form>
                ) : (
                  <span className="text-sm text-text-muted">{t("concierge.assignedYes")}</span>
                )}
              </Card>
            ))}
          </ul>
        )}
      </div>
      {res.ok ? <CursorPager basePath={base} params={filters} nextCursor={res.value.page.next_cursor} isFirst={!cursor} nextLabel={t("common.next")} firstLabel={t("common.firstPage")} navLabel={t("a11y.pagination")} /> : null}
    </>
  );
}
