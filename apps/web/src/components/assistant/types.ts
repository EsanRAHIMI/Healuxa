/**
 * Client-safe assistant types and helpers (no server imports). Card shapes come from
 * ai.openapi.yaml via @healuxa/api-client; labels are translated on the server and passed in.
 */
import type { AiCard, AiTurn } from "@healuxa/api-client";

export type ChatTurn = Pick<AiTurn, "id" | "role" | "content" | "cards" | "guardrail">;

export interface CardLabels {
  book: string;
  viewProfile: string;
  viewClinic: string;
  openStep: string;
  viewBooking: string;
  openRequest: string;
  priceFrom: string;
  priceOnRequest: string;
  duration: string;
  nextSlots: string;
  linkedStep: string;
  with: string;
  caseTitle: string;
  caseDue: string;
  handoffTitle: string;
  handoffBody: string;
  handoffCta: string;
  journeyStep: string;
  appointment: string;
  service: string;
  provider: string;
  facility: string;
}

export interface CardVocabulary {
  /** Step code -> label template with an optional {goal} placeholder. */
  steps: Record<string, string>;
  goals: Record<string, string>;
  stepStatus: Record<string, string>;
  appointmentStatus: Record<string, string>;
  caseStatus: Record<string, string>;
  facilityType: Record<string, string>;
}

export interface ChatLabels {
  title: string;
  newChat: string;
  talkToPerson: string;
  inputLabel: string;
  placeholder: string;
  send: string;
  sending: string;
  charCount: string;
  sendHint: string;
  startersTitle: string;
  emptyTitle: string;
  emptyBody: string;
  you: string;
  assistantName: string;
  replied: string;
  messagesLabel: string;
  notice: string;
  status: Record<string, string>;
  error: ErrorLabels;
}

export interface ErrorLabels {
  unavailable: string;
  rateLimited: string;
  tooLong: string;
  signedOut: string;
  notFound: string;
  full: string;
  generic: string;
  retry: string;
  notEnabled: string;
  unavailableTitle: string;
}

export type SseEvent = { event: string; data: Record<string, unknown> };

/** Split a buffer of SSE text into complete events; returns the unconsumed remainder. */
export function parseSseChunk(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) continue;
    try {
      events.push({ event, data: JSON.parse(data.join("\n")) as Record<string, unknown> });
    } catch {
      // ignore a malformed event rather than breaking the conversation
    }
  }
  return { events, rest };
}

/** Card links are server-built paths; only same-site relative paths are ever followed. */
export function cardHref(locale: string, href: string | undefined | null): string | null {
  if (!href || !href.startsWith("/") || href.startsWith("//") || href.includes("\\")) return null;
  return `/${locale}${href}`;
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

export function formatCardMoney(price: { amount_minor: number; currency: string }, intlLocale: string): string {
  return new Intl.NumberFormat(intlLocale, { style: "currency", currency: price.currency, currencyDisplay: "code" }).format(price.amount_minor / 100);
}

export function formatInZone(iso: string, intlLocale: string, timeZone: string | null | undefined): string {
  try {
    return new Intl.DateTimeFormat(intlLocale, { dateStyle: "medium", timeStyle: "short", ...(timeZone ? { timeZone } : {}) }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export type { AiCard };
