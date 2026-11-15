import { newIdempotencyKey } from "@healuxa/api-client";
import type { Metadata } from "next";

import { closeJourneyAction, startJourneyAction } from "@/actions/journey";
import { ServiceError, settle } from "@/components/domain/ServiceError";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { CheckboxField, SubmitButton } from "@/components/forms/fields";
import { Form } from "@/components/forms/Form";
import { AutoRefresh } from "@/components/journey/AutoRefresh";
import { JourneyTimeline, stepHref } from "@/components/journey/JourneyTimeline";
import { Alert, Badge, ButtonLink, Card, PageHeader, Section } from "@/components/ui/primitives";
import { getSession } from "@/lib/auth/session";
import { getT, resolveLocale } from "@/lib/i18n";
import { GOAL_CODES, isGoalCode, stepLabel } from "@/lib/journey";
import { loadJourney } from "@/lib/journey-server";
import { qp } from "@/lib/query";
import { privateMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("journey.title"));
}

/**
 * The customer's journey: pick goals, then follow one plan from intake through consultation, care
 * and follow-up. Plan data comes from transformation-engine; nothing here is computed client-side.
 */
export default async function JourneyPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const session = await getSession();
  const header = <PageHeader eyebrow={t("journey.eyebrow")} title={t("journey.title")} lead={t("journey.lead")} />;
  const note = (
    <Alert tone="info" role="note" className="mb-8 max-w-3xl">
      {t("journey.coordinationNote")}
    </Alert>
  );

  if (!session) {
    return (
      <div className="hx-container py-12">
        {header}
        {note}
        <Card className="max-w-xl">
          <h2 className="text-xl">{t("journey.signedOutTitle")}</h2>
          <p className="mt-2 text-text-muted">{t("journey.signedOutBody")}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <ButtonLink href={`/${locale}/login?next=${encodeURIComponent(`/${locale}/journey`)}`}>{t("auth.signIn")}</ButtonLink>
            <ButtonLink href={`/${locale}/register`} variant="secondary">
              {t("auth.signUp")}
            </ButtonLink>
          </div>
        </Card>
      </div>
    );
  }

  const res = await settle(() => loadJourney(session.userId));
  if (!res.ok) {
    return (
      <div className="hx-container py-12">
        {header}
        <ServiceError error={res.error} locale={locale} />
      </div>
    );
  }

  if (!res.value) {
    return (
      <div className="hx-container py-12">
        {header}
        {note}
        <Section title={t("journey.chooseTitle")} description={t("journey.chooseLead")} id="goals">
          <Form action={startJourneyAction} locale={locale} label={t("journey.chooseTitle")} showSuccess={false} hidden={{ idempotency_key: newIdempotencyKey("journey") }} testId="journey-start-form">
            <fieldset>
              <legend className="sr-only">{t("journey.goalsLegend")}</legend>
              <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {GOAL_CODES.map((goal) => (
                  <Card as="li" key={goal} className="has-[:checked]:border-primary has-[:checked]:bg-primary-soft">
                    <CheckboxField name="goals" id={`goal-${goal}`} value={goal} label={t(`journey.goal.${goal}`)} hint={t(`journey.goalBody.${goal}`)} data-testid={`goal-${goal}`} />
                  </Card>
                ))}
              </ul>
            </fieldset>
            <div className="mt-6">
              <SubmitButton pendingLabel={t("journey.starting")} testId="journey-start">
                {t("journey.startButton")}
              </SubmitButton>
            </div>
          </Form>
        </Section>
      </div>
    );
  }

  const { journey, phases } = res.value;
  const steps = phases.flatMap((p) => p.milestones);
  const done = steps.filter((s) => s.status === "completed").length;
  const current = phases.find((p) => p.status === "in_progress");
  const next = current?.milestones.find((s) => s.status === "pending");
  const nextHref = next ? stepHref(locale, next) : null;
  const intake = steps.find((s) => s.code === "intake_assessment");
  const updating = qp(await searchParams, "updated") === "1" && intake?.status !== "completed";

  return (
    <div className="hx-container py-12">
      {header}
      {updating ? (
        <>
          <AutoRefresh />
          <Alert tone="success" role="status" className="mb-6 max-w-3xl">
            {t("journey.updating")}
          </Alert>
        </>
      ) : null}
      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
        <section aria-labelledby="plan-title">
          <h2 id="plan-title" className="mb-4 text-2xl">
            {t("journey.timelineTitle")}
          </h2>
          <JourneyTimeline journey={journey} phases={phases} updating={updating} locale={locale} />
        </section>
        <aside className="space-y-6">
          <Card data-testid="journey-summary">
            <h2 className="text-lg">{t("journey.yourGoals")}</h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {(journey.primary_goals ?? []).map((goal) => (
                <li key={goal}>
                  <Badge tone="accent">{isGoalCode(goal) ? t(`journey.goal.${goal}`) : goal}</Badge>
                </li>
              ))}
            </ul>
            <p className="mt-5 text-sm font-medium" id="journey-progress-label">
              {t("journey.progress", { done, total: steps.length })}
            </p>
            <div
              role="progressbar"
              aria-labelledby="journey-progress-label"
              aria-valuemin={0}
              aria-valuemax={steps.length}
              aria-valuenow={done}
              className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted"
            >
              <div className="h-full rounded-full bg-primary" style={{ inlineSize: `${steps.length ? Math.round((done / steps.length) * 100) : 0}%` }} />
            </div>
          </Card>
          {next && !(updating && next.code === "intake_assessment") ? (
            <Card className="border-primary" data-testid="journey-next">
              <p className="text-sm font-medium tracking-wide text-accent uppercase">{t("journey.nextTitle")}</p>
              <p className="mt-2 text-lg font-medium">{stepLabel(t, next)}</p>
              {nextHref ? (
                <div className="mt-4">
                  <ButtonLink href={nextHref}>{next.code === "intake_assessment" ? t("journey.answerQuestions") : t("journey.findProviders")}</ButtonLink>
                </div>
              ) : null}
            </Card>
          ) : null}
          {steps.length > 0 && done === steps.length ? (
            <Alert tone="success" role="status" title={t("journey.allDoneTitle")}>
              {t("journey.allDoneBody")}
            </Alert>
          ) : null}
          <Alert tone="info" role="note">
            {t("journey.coordinationNote")}
          </Alert>
          <Card className="bg-surface-muted shadow-none">
            <h2 className="text-lg">{t("journey.endTitle")}</h2>
            <p className="mt-2 text-sm text-text-muted">{t("journey.endLead")}</p>
            <div className="mt-4">
              <Form action={closeJourneyAction} locale={locale} label={t("journey.endTitle")} showSuccess={false} hidden={{ journey_id: journey.id! }} testId="journey-end-form">
                <ConfirmButton
                  trigger={t("journey.endButton")}
                  title={t("journey.endTitle")}
                  description={t("journey.endConfirmBody")}
                  confirmLabel={t("journey.endButton")}
                  cancelLabel={t("common.cancel")}
                  testId="journey-end"
                />
              </Form>
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
