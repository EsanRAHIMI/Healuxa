import { formatDate, formatDateTime } from "@healuxa/i18n";

import { deleteRecordAction, revokeShareAction, shareRecordsAction } from "@/actions/records";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { expiryOptions, purposeOptions, shareLabels, typeOptions } from "@/components/records/labels";
import { ShareDialog } from "@/components/records/ShareDialog";
import { UploadForm } from "@/components/records/UploadForm";
import { Badge, Card, EmptyState, PageHeader } from "@/components/ui/primitives";
import { requireSession } from "@/lib/auth/session";
import { getCsrfToken } from "@/lib/csrf";
import { getT, resolveLocale } from "@/lib/i18n";
import { MAX_UPLOAD_BYTES, careTeam, formatBytes, listMyRecords, recentAccess } from "@/lib/records";

const HISTORY_SHOWN = 8;

/** Customer records: upload, list, download, share, stop sharing, delete, and who accessed what. */
export default async function RecordsPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const [records, access, team, csrf] = await Promise.all([
    settle(() => listMyRecords()),
    settle(() => recentAccess(100)),
    settle(() => careTeam(session.userId)),
    getCsrfToken(),
  ]);
  const mb = Math.round(MAX_UPLOAD_BYTES / (1024 * 1024));
  const typeLabel = (type: string) => t(`records.types.${type}`);
  const shareRecords = records.ok
    ? records.value.data.map((r) => ({ id: r.id, title: r.title, meta: typeLabel(r.type) }))
    : [];
  const candidates = team.ok ? team.value : [];
  const history = access.ok ? access.value : [];

  return (
    <>
      <PageHeader
        title={t("records.title")}
        lead={t("records.lead")}
        actions={
          shareRecords.length ? (
            <ShareDialog
              action={shareRecordsAction}
              csrf={csrf}
              locale={locale}
              records={shareRecords}
              preselected={[]}
              candidates={candidates}
              expiryOptions={expiryOptions(t)}
              purposeOptions={purposeOptions(t)}
              labels={shareLabels(t, t("records.shareRecords"))}
              variant="primary"
              testId="share-records"
            />
          ) : null
        }
      />
      <p className="-mt-4 mb-8 text-sm text-text-muted">{t("records.privacyLine")}</p>

      <Card className="mb-8">
        <h2 className="mb-4 text-xl">{t("records.upload.title")}</h2>
        <UploadForm
          csrf={csrf}
          maxBytes={MAX_UPLOAD_BYTES}
          types={typeOptions(t)}
          labels={{
            file: t("records.upload.file"),
            fileHint: t("records.upload.fileHint", { mb }),
            docTitle: t("records.upload.docTitle"),
            type: t("records.upload.type"),
            date: t("records.upload.date"),
            note: t("records.upload.note"),
            optional: t("common.optional"),
            submit: t("records.upload.submit"),
            uploading: t("records.upload.uploading"),
            done: t("records.upload.done"),
            chooseFile: t("records.upload.chooseFile"),
            tooLarge: t("records.upload.tooLarge", { mb }),
            wrongType: t("records.upload.wrongType"),
            failed: t("records.upload.failed"),
            full: t("records.upload.full"),
            signIn: t("errors.unauthorized"),
          }}
        />
        {records.ok ? (
          <p className="mt-4 text-sm text-text-muted hx-ltr-nums">
            {t("records.upload.usage", {
              count: records.value.usage.record_count,
              used: formatBytes(records.value.usage.total_bytes, locale),
              total: formatBytes(records.value.usage.max_total_bytes, locale),
            })}
          </p>
        ) : null}
      </Card>

      {!records.ok ? (
        <ServiceError error={records.error} locale={locale} />
      ) : records.value.data.length === 0 ? (
        <EmptyState title={t("records.empty")} body={t("records.emptyBody")} />
      ) : (
        <ul className="space-y-5" data-testid="records-list">
          {records.value.data.map((r) => {
            const events = history.filter((e) => e.record_id === r.id);
            return (
              <Card as="li" key={r.id} data-testid="record-card">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="text-lg break-words">{r.title}</h2>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                      <Badge>{typeLabel(r.type)}</Badge>
                      {r.document_date ? <span>{t("records.dated", { date: formatDate(r.document_date, locale) })}</span> : null}
                      <span>{t("records.uploadedOn", { date: formatDate(r.created_at, locale) })}</span>
                      <span className="hx-ltr-nums">{formatBytes(r.size_bytes, locale)}</span>
                    </p>
                    {r.note ? <p className="mt-2 text-sm">{r.note}</p> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <a href={`/api/records/${r.id}/content`} download className="inline-flex min-h-9 items-center rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-text no-underline hover:bg-surface-muted" data-testid="record-download">
                      {t("records.download")}
                    </a>
                    <ShareDialog
                      action={shareRecordsAction}
                      csrf={csrf}
                      locale={locale}
                      records={shareRecords}
                      preselected={[r.id]}
                      candidates={candidates}
                      expiryOptions={expiryOptions(t)}
                      purposeOptions={purposeOptions(t)}
                      labels={shareLabels(t)}
                      testId="record-share"
                    />
                    <Form action={deleteRecordAction} locale={locale} hidden={{ record_id: r.id }} label={t("records.delete")}>
                      <ConfirmButton trigger={t("records.delete")} title={t("records.deleteTitle")} description={t("records.deleteBody")} confirmLabel={t("records.delete")} cancelLabel={t("common.cancel")} testId="record-delete" />
                    </Form>
                  </div>
                </div>

                <div className="mt-4 border-t border-border pt-4">
                  <h3 className="text-sm font-medium">{t("records.sharedWith")}</h3>
                  {r.shares.length ? (
                    <ul className="mt-2 space-y-2" data-testid="record-shares">
                      {r.shares.map((s) => (
                        <li key={s.grant_id} className="flex flex-wrap items-center justify-between gap-2">
                          <span>
                            <span className="font-medium">{s.grantee_name}</span>{" "}
                            <span className="text-sm text-text-muted">
                              · {t(`records.purposes.${s.purpose}`)} · {t("records.until", { date: formatDate(s.expires_at, locale) })}
                            </span>
                          </span>
                          <Form action={revokeShareAction} locale={locale} hidden={{ grant_id: s.grant_id, record_id: r.id }} label={t("records.revoke")} showSuccess={false}>
                            <SubmitButton variant="ghost" pendingLabel={t("common.saving")} testId="record-revoke">
                              {t("records.revoke")}
                            </SubmitButton>
                          </Form>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-sm text-text-muted">{t("records.notShared")}</p>
                  )}
                </div>

                <details className="mt-4 border-t border-border pt-4" data-testid="record-history">
                  <summary className="cursor-pointer text-sm font-medium">{t("records.history")}</summary>
                  {events.length ? (
                    <ol className="mt-3 space-y-2 text-sm">
                      {events.slice(0, HISTORY_SHOWN).map((e) => (
                        <li key={e.id} className="flex flex-wrap gap-x-2">
                          <span className="hx-ltr-nums text-text-muted">{formatDateTime(e.occurred_at, locale, { dateStyle: "medium", timeStyle: "short" })}</span>
                          <span className={e.action === "denied" ? "font-medium text-danger" : "font-medium"}>{t(`records.actions.${e.action}`)}</span>
                          <span>
                            {e.organisation?.name ?? t(`records.actors.${e.actor.kind}`)}
                            {e.organisation && e.actor.kind !== "owner" ? ` · ${t(`records.actors.${e.actor.kind}`)}` : ""}
                          </span>
                          {e.client.agent && e.actor.kind !== "owner" ? <span className="text-text-muted">{t("records.via", { client: e.client.agent })}</span> : null}
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-2 text-sm text-text-muted">{t("records.historyEmpty")}</p>
                  )}
                </details>
              </Card>
            );
          })}
        </ul>
      )}
    </>
  );
}
