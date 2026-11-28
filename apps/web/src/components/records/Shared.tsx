import { ForbiddenError, NotFoundError, unwrap } from "@healuxa/api-client";
import { formatDate, type Locale } from "@healuxa/i18n";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ServiceError, settle } from "@/components/domain/ServiceError";
import { Badge, ButtonLink, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { getT } from "@/lib/i18n";
import { ID_RE, formatBytes } from "@/lib/records";

const shortRef = (id: string) => id.slice(-6).toUpperCase();

/** "Shared with me" for one organisation: active grants only, patient-scoped, expiry always visible. */
export async function SharedList({ locale, granteeType, granteeId, basePath }: { locale: Locale; granteeType: "provider" | "facility"; granteeId: string; basePath: string }) {
  const t = getT(locale);
  const api = await userApi();
  const result = await settle(() => unwrap(api.profile.GET("/shared-records", { params: { query: { grantee_type: granteeType, grantee_id: granteeId } } })));
  return (
    <>
      <PageHeader title={t("records.sharedWithMe")} />
      <p className="-mt-4 mb-8 text-sm text-text-muted">{t("records.sharedLead")}</p>
      {!result.ok ? (
        <ServiceError error={result.error} locale={locale} />
      ) : result.value.data.length === 0 ? (
        <EmptyState title={t("records.sharedEmpty")} />
      ) : (
        <ul className="space-y-4" data-testid="shared-list">
          {result.value.data.map((g) => (
            <Card as="li" key={g.id} className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="font-medium">
                  {t("records.patientRef", { ref: shortRef(g.patient_user_id) })}{" "}
                  <span className="text-sm font-normal text-text-muted">· {t(`records.purposes.${g.purpose}`)}</span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                  <span>{t("records.documents", { count: g.record_count })}</span>
                  <Badge tone="info" className="hx-ltr-nums">{t("records.expires", { date: formatDate(g.expires_at, locale) })}</Badge>
                  {g.appointment_id ? <span>{t("records.fromBooking")}</span> : null}
                </p>
              </div>
              <ButtonLink href={`${basePath}/${g.id}`} variant="secondary" size="sm" data-testid="shared-open">
                {t("records.open")}
              </ButtonLink>
            </Card>
          ))}
        </ul>
      )}
    </>
  );
}

/** One grant's documents (each open is logged as a view for the patient). */
export async function SharedDetail({ locale, grantId, backHref }: { locale: Locale; grantId: string; backHref: string }) {
  if (!ID_RE.test(grantId)) notFound();
  const t = getT(locale);
  const api = await userApi();
  let detail;
  try {
    detail = await unwrap(api.profile.GET("/shared-records/{grant_id}", { params: { path: { grant_id: grantId } } }));
  } catch (error) {
    if (error instanceof NotFoundError) notFound();
    if (error instanceof ForbiddenError) {
      return (
        <>
          <EmptyState title={t("records.noLongerShared")} action={<ButtonLink href={backHref} variant="secondary" size="sm">{t("records.backToShared")}</ButtonLink>} />
        </>
      );
    }
    return <ServiceError error={error} locale={locale} />;
  }
  return (
    <>
      <p className="mb-4 text-sm">
        <Link href={backHref}>{t("records.backToShared")}</Link>
      </p>
      <PageHeader
        title={t("records.patientRef", { ref: shortRef(detail.patient_user_id) })}
        lead={t(`records.purposes.${detail.purpose}`)}
        actions={<Badge tone="info" className="hx-ltr-nums">{t("records.expires", { date: formatDate(detail.expires_at, locale) })}</Badge>}
      />
      <ul className="space-y-4" data-testid="shared-records">
        {detail.records.map((r) => (
          <Card as="li" key={r.id} className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="font-medium break-words">{r.title}</p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                <Badge>{t(`records.types.${r.type}`)}</Badge>
                {r.document_date ? <span>{t("records.dated", { date: formatDate(r.document_date, locale) })}</span> : null}
                <span className="hx-ltr-nums" dir="ltr">{formatBytes(r.size_bytes, locale)}</span>
              </p>
              {r.note ? <p className="mt-2 text-sm">{r.note}</p> : null}
            </div>
            <a href={`/api/records/${r.id}/content`} download className="inline-flex min-h-9 items-center rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-text no-underline hover:bg-surface-muted" data-testid="shared-download">
              {t("records.download")}
            </a>
          </Card>
        ))}
      </ul>
    </>
  );
}
