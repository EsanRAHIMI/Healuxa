import { newIdempotencyKey, type Journey, type JourneyMilestone, type RoadmapPhase } from "@healuxa/api-client";
import { formatDate, formatDateTime, type Locale } from "@healuxa/i18n";

import { completeStepAction } from "@/actions/journey";
import { CheckIcon } from "@/components/domain/badges";
import { ConfirmButton } from "@/components/forms/ConfirmButton";
import { Form } from "@/components/forms/Form";
import { cn } from "@/components/ui/cn";
import { Badge, ButtonLink, Card } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";
import { BOOKABLE_STEPS, phaseLabel, stepLabel } from "@/lib/journey";

const STEP_TONE = { pending: "warning", scheduled: "info", in_progress: "info", completed: "success", blocked: "neutral" } as const;
const PHASE_TONE = { pending: "neutral", in_progress: "primary", completed: "success" } as const;

/** Where a step sends the customer: the intake form, or the catalogue filtered to the step's category. */
export function stepHref(locale: Locale, step: JourneyMilestone): string | null {
  if (step.code === "intake_assessment") return `/${locale}/journey/intake`;
  if (step.code && BOOKABLE_STEPS.includes(step.code) && step.service_category) {
    return `/${locale}/services?category=${encodeURIComponent(step.service_category)}&milestone=${step.id}`;
  }
  return null;
}

function StepActions({ journey, step, locale }: { journey: Journey; step: JourneyMilestone; locale: Locale }) {
  const t = getT(locale);
  const href = stepHref(locale, step);
  const bookable = !!step.code && BOOKABLE_STEPS.includes(step.code);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {href ? (
        <ButtonLink href={href} size="sm" data-testid={`step-cta-${step.code}`}>
          {step.code === "intake_assessment" ? t("journey.answerQuestions") : t("journey.findProviders")}
        </ButtonLink>
      ) : null}
      {bookable ? (
        <ButtonLink href={`/${locale}/account/concierge#new`} variant="secondary" size="sm">
          {t("journey.askConcierge")}
        </ButtonLink>
      ) : null}
      {step.code !== "intake_assessment" ? (
        <Form
          action={completeStepAction}
          locale={locale}
          label={t("journey.markDone")}
          className="contents"
          hidden={{ journey_id: journey.id!, milestone_id: step.id!, idempotency_key: newIdempotencyKey("step") }}
        >
          <ConfirmButton
            trigger={t("journey.markDone")}
            title={t("journey.markDoneTitle")}
            description={t("journey.markDoneBody")}
            confirmLabel={t("journey.markDone")}
            cancelLabel={t("common.cancel")}
            variant="secondary"
            testId={`step-done-${step.code}`}
          />
        </Form>
      ) : null}
    </div>
  );
}

function Step({ journey, step, current, updating, locale }: { journey: Journey; step: JourneyMilestone; current: boolean; updating: boolean; locale: Locale }) {
  const t = getT(locale);
  const status = (step.status ?? "pending") as keyof typeof STEP_TONE;
  const done = status === "completed";
  const code = step.code ?? "other";
  return (
    <li className="flex gap-3 py-4 first:pt-0 last:pb-0" data-testid="journey-step" data-code={code} data-status={status}>
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border",
          done ? "border-success bg-success-soft text-success" : current ? "border-primary" : "border-border-strong",
        )}
      >
        {done ? <CheckIcon className="size-3.5" /> : null}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className={cn("text-base font-medium", !current && !done && "text-text-muted")}>{stepLabel(t, step)}</h4>
          {current || status !== "pending" ? <Badge tone={STEP_TONE[status] ?? "neutral"}>{t(`journey.stepStatus.${status in STEP_TONE ? status : "pending"}`)}</Badge> : null}
        </div>
        {done ? (
          step.completed_at ? <p className="mt-1 text-sm text-text-muted">{t("journey.completedOn", { date: formatDate(step.completed_at, locale) })}</p> : null
        ) : status === "scheduled" ? (
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2">
            {step.scheduled_at ? (
              <p className="text-sm">{t("journey.scheduledFor", { date: formatDateTime(step.scheduled_at, locale, { dateStyle: "medium", timeStyle: "short" }) })}</p>
            ) : null}
            {step.appointment_id ? (
              <ButtonLink href={`/${locale}/account/bookings/${step.appointment_id}`} variant="secondary" size="sm">
                {t("journey.viewAppointment")}
              </ButtonLink>
            ) : null}
          </div>
        ) : (
          <>
            <p className="mt-1 text-sm text-text-muted">{t(`journey.stepBody.${["intake_assessment", "consultation", "care", "follow_up", "progress_review"].includes(code) ? code : "other"}`)}</p>
            {current && status === "pending" && !(updating && code === "intake_assessment") ? <StepActions journey={journey} step={step} locale={locale} /> : null}
          </>
        )}
      </div>
    </li>
  );
}

/** The plan as an ordered timeline: four stages, each with its steps and the action each step needs. */
export function JourneyTimeline({ journey, phases, updating, locale }: { journey: Journey; phases: RoadmapPhase[]; updating: boolean; locale: Locale }) {
  const t = getT(locale);
  return (
    <ol className="space-y-5" data-testid="journey-timeline">
      {phases.map((phase, index) => {
        const status = phase.status as keyof typeof PHASE_TONE;
        const current = status === "in_progress";
        return (
          <Card as="li" key={phase.id} className={cn(current && "border-primary")} data-testid="journey-phase" data-code={phase.code ?? ""} data-status={status}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-baseline gap-3 text-xl">
                <span className="hx-ltr-nums text-sm font-medium text-accent">{String(index + 1).padStart(2, "0")}</span>
                {phaseLabel(t, phase)}
              </h3>
              <Badge tone={PHASE_TONE[status] ?? "neutral"}>{t(`journey.phaseStatus.${status in PHASE_TONE ? status : "pending"}`)}</Badge>
            </div>
            {status === "pending" ? <p className="mb-4 text-sm text-text-muted">{t("journey.laterStage")}</p> : null}
            <ul className="divide-y divide-border">
              {phase.milestones.map((step) => (
                <Step key={step.id} journey={journey} step={step} current={current} updating={updating} locale={locale} />
              ))}
            </ul>
          </Card>
        );
      })}
    </ol>
  );
}
