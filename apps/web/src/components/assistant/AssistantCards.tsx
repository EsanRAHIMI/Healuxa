"use client";

import Link from "next/link";

import { Badge, buttonClass } from "@/components/ui/primitives";

import { cardHref, fill, formatCardMoney, formatInZone, type AiCard, type CardLabels, type CardVocabulary } from "./types";

/**
 * Action cards from the assistant's structured payload. Every value shown here (names, prices,
 * slots, links) was built server-side from verified tool data — nothing is taken from model text.
 * Booking happens on the normal booking page the card links to.
 */
export function AssistantCards({
  cards,
  locale,
  intlLocale,
  labels,
  vocab,
}: {
  cards: AiCard[];
  locale: string;
  intlLocale: string;
  labels: CardLabels;
  vocab: CardVocabulary;
}) {
  if (!cards.length) return null;
  return (
    <ul className="mt-3 grid gap-3 sm:grid-cols-2" data-testid="assistant-cards">
      {cards.map((card, i) => (
        <li key={`${card.kind}-${"id" in card ? card.id : i}`} className="rounded-lg border border-border bg-surface p-4 shadow-sm" data-testid={`card-${card.kind}`}>
          <CardBody card={card} locale={locale} intlLocale={intlLocale} labels={labels} vocab={vocab} />
        </li>
      ))}
    </ul>
  );
}

function Cta({ href, locale, label, variant = "primary" }: { href: string | null | undefined; locale: string; label: string; variant?: "primary" | "secondary" }) {
  const target = cardHref(locale, href);
  if (!target) return null;
  return (
    <div className="mt-3">
      <Link href={target} className={buttonClass(variant, "sm")}>
        {label}
      </Link>
    </div>
  );
}

function Kind({ children }: { children: string }) {
  return <p className="text-xs font-medium tracking-wide text-text-muted uppercase">{children}</p>;
}

function stepTitle(vocab: CardVocabulary, code: string | null | undefined, goal: string | null | undefined): string {
  const template = (code && vocab.steps[code]) || vocab.steps.other || "";
  return fill(template, { goal: (goal && vocab.goals[goal]) || "" }).replace(/\s+[—-]\s*$/, "");
}

function CardBody({ card, locale, intlLocale, labels, vocab }: { card: AiCard; locale: string; intlLocale: string; labels: CardLabels; vocab: CardVocabulary }) {
  switch (card.kind) {
    case "service": {
      const price =
        card.price_type === "on_request" || !card.price
          ? labels.priceOnRequest
          : card.price_type === "from"
            ? fill(labels.priceFrom, { price: formatCardMoney(card.price, intlLocale) })
            : formatCardMoney(card.price, intlLocale);
      return (
        <>
          <Kind>{labels.service}</Kind>
          <p className="mt-1 font-medium">{card.title}</p>
          {card.provider_name ? <p className="text-sm text-text-muted">{fill(labels.with, { name: card.provider_name })}</p> : null}
          <p className="mt-2 text-sm">
            <span className="hx-ltr-nums font-semibold">{price}</span>
            {card.duration_minutes ? <span className="text-text-muted"> · {fill(labels.duration, { minutes: card.duration_minutes })}</span> : null}
          </p>
          {card.next_slots.length ? (
            <div className="mt-2 text-sm">
              <p className="text-text-muted">{labels.nextSlots}</p>
              <ul className="mt-1 space-y-0.5">
                {card.next_slots.map((slot) => (
                  <li key={slot} className="hx-ltr-nums">
                    {formatInZone(slot, intlLocale, card.timezone)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {card.milestone_id ? (
            <p className="mt-2">
              <Badge tone="accent">{labels.linkedStep}</Badge>
            </p>
          ) : null}
          <Cta href={card.href} locale={locale} label={labels.book} />
        </>
      );
    }
    case "provider":
      return (
        <>
          <Kind>{labels.provider}</Kind>
          <p className="mt-1 font-medium">{card.title}</p>
          {card.subtitle ? <p className="text-sm text-text-muted">{card.subtitle}</p> : null}
          {card.specialties?.length ? <p className="mt-1 text-sm">{card.specialties.join(" · ")}</p> : null}
          <Cta href={card.href} locale={locale} label={labels.viewProfile} variant="secondary" />
        </>
      );
    case "facility":
      return (
        <>
          <Kind>{labels.facility}</Kind>
          <p className="mt-1 font-medium">{card.title}</p>
          {card.facility_type ? <p className="text-sm text-text-muted">{vocab.facilityType[card.facility_type] ?? card.facility_type}</p> : null}
          <Cta href={card.href} locale={locale} label={labels.viewClinic} variant="secondary" />
        </>
      );
    case "journey_step":
      return (
        <>
          <Kind>{labels.journeyStep}</Kind>
          <p className="mt-1 font-medium">{stepTitle(vocab, card.code, card.goal)}</p>
          {card.status ? <p className="text-sm text-text-muted">{vocab.stepStatus[card.status] ?? card.status}</p> : null}
          <Cta href={card.href} locale={locale} label={labels.openStep} />
        </>
      );
    case "appointment":
      return (
        <>
          <Kind>{labels.appointment}</Kind>
          <p className="mt-1 font-medium">{card.title}</p>
          {card.scheduled_at ? <p className="hx-ltr-nums text-sm">{formatInZone(card.scheduled_at, intlLocale, card.timezone)}</p> : null}
          {card.status ? <p className="text-sm text-text-muted">{vocab.appointmentStatus[card.status] ?? card.status}</p> : null}
          <Cta href={card.href} locale={locale} label={labels.viewBooking} variant="secondary" />
        </>
      );
    case "concierge_case":
      return (
        <>
          <p className="font-medium">{labels.caseTitle}</p>
          {card.status ? <p className="text-sm text-text-muted">{vocab.caseStatus[card.status] ?? card.status}</p> : null}
          {card.first_response_due_at ? (
            <p className="hx-ltr-nums text-sm">{fill(labels.caseDue, { due: formatInZone(card.first_response_due_at, intlLocale, null) })}</p>
          ) : null}
          <Cta href={card.href} locale={locale} label={labels.openRequest} />
        </>
      );
    case "handoff":
      return (
        <>
          <p className="font-medium">{labels.handoffTitle}</p>
          <p className="text-sm text-text-muted">{labels.handoffBody}</p>
          <Cta href={card.href} locale={locale} label={labels.handoffCta} variant="secondary" />
        </>
      );
    default:
      return null;
  }
}
