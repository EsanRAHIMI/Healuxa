import { NotFoundError, unwrap, type AiSession } from "@healuxa/api-client";
import { catalogs, intlLocale, type Locale, type MessageTree } from "@healuxa/i18n";
import type { Metadata } from "next";

import { AssistantChat } from "@/components/assistant/AssistantChat";
import type { CardLabels, CardVocabulary, ChatLabels, ChatTurn, ErrorLabels } from "@/components/assistant/types";
import { Alert, ButtonLink, PageHeader } from "@/components/ui/primitives";
import { userApi } from "@/lib/api";
import { hasPermission, requireSession } from "@/lib/auth/session";
import { getCsrfToken } from "@/lib/csrf";
import { getT, resolveLocale } from "@/lib/i18n";
import { BOOKABLE_STEPS, isGoalCode } from "@/lib/journey";
import { loadJourney } from "@/lib/journey-server";
import { qp } from "@/lib/query";
import { privateMetadata } from "@/lib/seo";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

const SESSION_ID = /^[0-9A-HJKMNP-TV-Z]{26}$/;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  return privateMetadata(locale, getT(locale)("assistant.title"));
}

/** Raw (unformatted) catalog subtree, English as fallback, for labels the client fills in itself. */
function rawTree(locale: Locale, path: string): Record<string, unknown> {
  const pick = (tree: MessageTree | undefined) =>
    path.split(".").reduce<unknown>((node, key) => (node && typeof node === "object" ? (node as Record<string, unknown>)[key] : undefined), tree);
  const en = (pick(catalogs.en) ?? {}) as Record<string, unknown>;
  const own = (pick(catalogs[locale]) ?? {}) as Record<string, unknown>;
  const merge = (a: Record<string, unknown>, b: Record<string, unknown>): Record<string, unknown> => {
    const out: Record<string, unknown> = { ...a };
    for (const [k, v] of Object.entries(b)) out[k] = v && typeof v === "object" && typeof a[k] === "object" ? merge(a[k] as Record<string, unknown>, v as Record<string, unknown>) : v;
    return out;
  };
  return merge(en, own);
}

async function loadSession(id: string | undefined): Promise<AiSession | null> {
  if (!id || !SESSION_ID.test(id)) return null;
  const api = await userApi();
  return unwrap(api.ai.GET("/ai/sessions/{id}", { params: { path: { id } } })).catch((e) => {
    if (e instanceof NotFoundError) return null;
    throw e;
  });
}

/**
 * Customer assistant. The page renders a resumed conversation (?s=) and journey-aware starter
 * prompts on the server; replies stream through the BFF route /api/assistant/messages.
 */
export default async function AssistantPage({ params, searchParams }: Props) {
  const locale = await resolveLocale(params);
  const session = await requireSession(locale);
  const t = getT(locale);
  const header = <PageHeader eyebrow={t("assistant.eyebrow")} title={t("assistant.title")} lead={t("assistant.lead")} />;
  const handoffHref = `/${locale}/account/concierge#new`;

  if (!hasPermission(session, "ai:chat")) {
    return (
      <div className="hx-container py-12">
        {header}
        <Alert tone="info" role="note" className="max-w-3xl">
          <p>{t("assistant.error.notEnabled")}</p>
        </Alert>
        <div className="mt-4">
          <ButtonLink href={handoffHref} variant="secondary">
            {t("assistant.talkToPerson")}
          </ButtonLink>
        </div>
      </div>
    );
  }

  const sp = await searchParams;
  const [resumed, journey] = await Promise.all([
    loadSession(qp(sp, "s")).catch(() => null),
    loadJourney(session.userId).catch(() => null),
  ]);

  // Starter prompts follow the journey: the next bookable step first, otherwise a gentle start.
  const steps = journey?.phases.flatMap((p) => p.milestones) ?? [];
  const nextBookable = steps.find((s) => s.status === "pending" && s.code && BOOKABLE_STEPS.includes(s.code));
  const starters = journey
    ? [
        t("assistant.starter.nextStep"),
        ...(nextBookable?.goal && isGoalCode(nextBookable.goal) ? [t("assistant.starter.bookNext", { goal: t(`journey.goal.${nextBookable.goal}`) })] : []),
        t("assistant.starter.appointments"),
        t("assistant.starter.person"),
      ]
    : [t("assistant.starter.startJourney"), t("assistant.starter.dental"), t("assistant.starter.appointments"), t("assistant.starter.person")];

  const a = rawTree(locale, "assistant") as Record<string, unknown> & { status: Record<string, string>; error: ErrorLabels; card: Record<string, string> };
  const labels: ChatLabels = {
    title: String(a.title),
    newChat: String(a.newChat),
    talkToPerson: String(a.talkToPerson),
    inputLabel: String(a.inputLabel),
    placeholder: String(a.placeholder),
    send: String(a.send),
    sending: String(a.sending),
    charCount: String(a.charCount),
    sendHint: String(a.sendHint),
    startersTitle: String(a.startersTitle),
    emptyTitle: String(a.emptyTitle),
    emptyBody: String(a.emptyBody),
    you: String(a.you),
    assistantName: String(a.assistantName),
    replied: String(a.replied),
    messagesLabel: String(a.messagesLabel),
    notice: String(a.notice),
    status: a.status,
    error: a.error,
  };
  const vocab: CardVocabulary = {
    steps: rawTree(locale, "journey.step") as Record<string, string>,
    goals: rawTree(locale, "journey.goal") as Record<string, string>,
    stepStatus: rawTree(locale, "journey.stepStatus") as Record<string, string>,
    appointmentStatus: rawTree(locale, "enums.appointmentStatus") as Record<string, string>,
    caseStatus: rawTree(locale, "enums.caseStatus") as Record<string, string>,
    facilityType: rawTree(locale, "enums.facilityType") as Record<string, string>,
  };
  const turns: ChatTurn[] = (resumed?.turns ?? []).map((turn) => ({ id: turn.id, role: turn.role, content: turn.content, cards: turn.cards, guardrail: turn.guardrail ?? null }));

  return (
    <div className="hx-container py-12">
      {header}
      <div className="max-w-4xl">
        <AssistantChat
          locale={locale}
          intlLocale={intlLocale(locale)}
          csrf={await getCsrfToken()}
          initialSessionId={resumed?.id ?? null}
          initialTurns={turns}
          available={resumed ? resumed.assistant_available : true}
          maxChars={resumed?.max_message_chars ?? 2000}
          starters={starters}
          labels={labels}
          cardLabels={a.card as unknown as CardLabels}
          vocab={vocab}
          handoffHref={handoffHref}
        />
      </div>
    </div>
  );
}
