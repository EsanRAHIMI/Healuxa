import type { Affiliation } from "@healuxa/api-client";
import { formatDate, type Locale } from "@healuxa/i18n";

import { decideAffiliationAction } from "@/actions/provider";
import { StatusBadge } from "@/components/domain/badges";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { Card, EmptyState } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

/** Affiliation handshake list. Only the counterparty may approve/decline; either side may end an active one. */
export function AffiliationList({
  affiliations,
  side,
  locale,
  labelFor,
}: {
  affiliations: Affiliation[];
  side: "provider" | "facility";
  locale: Locale;
  labelFor: (a: Affiliation) => { title: string; subtitle?: string };
}) {
  const t = getT(locale);
  if (affiliations.length === 0) return <EmptyState title={t("pp.noAffiliations")} body={side === "provider" ? t("pp.noAffiliationsBody") : t("fp.noAffiliationsBody")} />;
  return (
    <ul className="space-y-3" data-testid="affiliations">
      {affiliations.map((a) => {
        const label = labelFor(a);
        const awaitingMe = a.status === "pending" && a.initiated_by !== side;
        return (
          <Card as="li" key={a.id} className="flex flex-wrap items-center justify-between gap-4" data-testid="affiliation">
            <div>
              <p className="font-medium">{label.title}</p>
              {label.subtitle ? <p className="text-sm text-text-muted">{label.subtitle}</p> : null}
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                <StatusBadge status={a.status} kind="affiliationStatus" locale={locale} />
                <span>{t(`enums.initiatedBy.${a.initiated_by}`)}</span>
                {a.created_at ? <span>· {formatDate(a.created_at, locale)}</span> : null}
              </p>
              {a.status === "pending" && !awaitingMe ? <p className="mt-1 text-sm text-text-muted">{t("pp.awaitingOther")}</p> : null}
            </div>
            {awaitingMe ? (
              <Form action={decideAffiliationAction} locale={locale} hidden={{ affiliation_id: a.id }} label={t("pp.decide")}>
                <div className="flex flex-wrap gap-2">
                  <SubmitButton name="decision" value="approve" pendingLabel={t("common.saving")} testId="affiliation-approve">
                    {t("pp.approve")}
                  </SubmitButton>
                  <SubmitButton name="decision" value="decline" variant="secondary" pendingLabel={t("common.saving")}>
                    {t("pp.decline")}
                  </SubmitButton>
                </div>
              </Form>
            ) : a.status === "active" ? (
              <Form action={decideAffiliationAction} locale={locale} hidden={{ affiliation_id: a.id }} label={t("pp.endAffiliation")}>
                <ConfirmButton
                  trigger={t("pp.endAffiliation")}
                  title={t("pp.endTitle")}
                  description={t("pp.endBody")}
                  confirmLabel={t("pp.endAffiliation")}
                  cancelLabel={t("common.cancel")}
                  name="decision"
                  value="end"
                />
              </Form>
            ) : null}
          </Card>
        );
      })}
    </ul>
  );
}
