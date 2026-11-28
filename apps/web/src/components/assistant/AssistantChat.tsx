"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Alert, Button, buttonClass } from "@/components/ui/primitives";
import { cn } from "@/components/ui/cn";

import { AssistantCards } from "./AssistantCards";
import { fill, parseSseChunk, type AiCard, type CardLabels, type CardVocabulary, type ChatLabels, type ChatTurn } from "./types";

interface Pending {
  text: string;
  status: string | null;
}

interface Failure {
  message: string;
  retry: { content: string; key: string } | null;
  fatal?: boolean;
}

function newKey(): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return `ai-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

/**
 * Streamed assistant conversation. Talks only to the BFF route (/api/assistant/messages), which
 * forwards the httpOnly-cookie token to ai-orchestrator; the browser never sees a token.
 */
export function AssistantChat({
  locale,
  intlLocale,
  csrf,
  initialSessionId,
  initialTurns,
  available,
  maxChars,
  starters,
  labels,
  cardLabels,
  vocab,
  handoffHref,
}: {
  locale: string;
  intlLocale: string;
  csrf: string;
  initialSessionId: string | null;
  initialTurns: ChatTurn[];
  available: boolean;
  maxChars: number;
  starters: string[];
  labels: ChatLabels;
  cardLabels: CardLabels;
  vocab: CardVocabulary;
  handoffHref: string;
}) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [turns, setTurns] = useState<ChatTurn[]>(initialTurns);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [failure, setFailure] = useState<Failure | null>(available ? null : { message: labels.error.unavailable, retry: null, fatal: true });
  const [announce, setAnnounce] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputId = useId();
  const hintId = useId();
  const busy = pending !== null;

  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, pending?.text]);

  const rememberSession = useCallback((id: string) => {
    setSessionId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("s", id);
    window.history.replaceState(window.history.state, "", url);
  }, []);

  const errorFor = useCallback(
    (code: string | undefined): string => {
      switch (code) {
        case "service_unavailable":
          return labels.error.unavailable;
        case "rate_limited":
          return labels.error.rateLimited;
        case "validation_error":
          return labels.error.tooLong;
        case "unauthorized":
          return labels.error.signedOut;
        case "forbidden":
          return labels.error.notEnabled;
        case "not_found":
          return labels.error.notFound;
        case "conflict":
          return labels.error.full;
        default:
          return labels.error.generic;
      }
    },
    [labels],
  );

  const send = useCallback(
    async (content: string, key: string = newKey()) => {
      const text = content.trim();
      if (!text || busy) return;
      setFailure(null);
      setAnnounce("");
      const userTurn: ChatTurn = { id: `local-${key}`, role: "user", content: text, cards: [], guardrail: null };
      setTurns((current) => [...current, userTurn]);
      setDraft("");
      setPending({ text: "", status: labels.status.working ?? null });
      const controller = new AbortController();
      abortRef.current = controller;
      let finished = false;
      const fail = (code: string | undefined, retryable: boolean) => {
        setTurns((current) => current.filter((t) => t.id !== userTurn.id));
        setDraft(text);
        setFailure({ message: errorFor(code), retry: retryable ? { content: text, key } : null, fatal: code === "forbidden" });
      };
      try {
        const res = await fetch("/api/assistant/messages", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "text/event-stream", "x-hx-csrf": csrf },
          body: JSON.stringify({ session_id: sessionId, content: text, locale, idempotency_key: key }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          const body = (await res.json().catch(() => ({}))) as { code?: string; session_id?: string };
          if (body.session_id) rememberSession(body.session_id);
          if (body.code === "not_found") setSessionId(null);
          fail(body.code, !["validation_error", "forbidden", "unauthorized"].includes(body.code ?? ""));
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamed = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseChunk(buffer);
          buffer = parsed.rest;
          for (const { event, data } of parsed.events) {
            if (event === "session" && typeof data.session_id === "string") rememberSession(data.session_id);
            else if (event === "status") setPending((p) => ({ text: p?.text ?? "", status: labels.status[String(data.tool)] ?? labels.status.working ?? null }));
            else if (event === "delta" && typeof data.text === "string") {
              streamed += data.text;
              setPending({ text: streamed, status: null });
            } else if (event === "replace" && typeof data.text === "string") {
              streamed = data.text;
              setPending({ text: streamed, status: null });
            } else if (event === "done" && data.turn) {
              const turn = data.turn as ChatTurn & { cards: AiCard[] };
              finished = true;
              setTurns((current) => [...current, { id: turn.id, role: "assistant", content: turn.content, cards: turn.cards ?? [], guardrail: turn.guardrail ?? null }]);
              setAnnounce(labels.replied);
            } else if (event === "error") {
              finished = true;
              fail(typeof data.code === "string" ? data.code : undefined, true);
            }
          }
        }
        if (!finished) fail(undefined, true);
      } catch (error) {
        if ((error as Error).name !== "AbortError") fail(undefined, true);
      } finally {
        abortRef.current = null;
        setPending(null);
        inputRef.current?.focus();
      }
    },
    [busy, csrf, errorFor, labels, locale, rememberSession, sessionId],
  );

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(draft);
    }
  };

  const reset = () => {
    abortRef.current?.abort();
    setSessionId(null);
    setTurns([]);
    setFailure(available ? null : { message: labels.error.unavailable, retry: null, fatal: true });
    setDraft("");
    const url = new URL(window.location.href);
    url.searchParams.delete("s");
    window.history.replaceState(window.history.state, "", url);
    inputRef.current?.focus();
  };

  const disabled = !available || failure?.fatal === true;

  return (
    <div className="flex flex-col gap-4" data-testid="assistant-chat">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {turns.length ? (
          <Button variant="ghost" size="sm" onClick={reset} disabled={busy} data-testid="assistant-new">
            {labels.newChat}
          </Button>
        ) : null}
        <Link href={handoffHref} className={buttonClass("secondary", "sm")} data-testid="assistant-handoff">
          {labels.talkToPerson}
        </Link>
      </div>

      <div className="min-h-64 rounded-lg border border-border bg-surface-muted p-4 md:p-6">
        {turns.length === 0 && !busy ? (
          <div className="py-6 text-center">
            <p className="text-lg font-medium">{labels.emptyTitle}</p>
            <p className="mx-auto mt-2 max-w-prose text-text-muted">{labels.emptyBody}</p>
            {starters.length && !disabled ? (
              <div className="mt-6">
                <p className="mb-3 text-sm text-text-muted" id={`${inputId}-starters`}>
                  {labels.startersTitle}
                </p>
                <ul className="flex flex-wrap justify-center gap-2" aria-labelledby={`${inputId}-starters`}>
                  {starters.map((prompt) => (
                    <li key={prompt}>
                      <Button variant="secondary" size="sm" onClick={() => void send(prompt)} data-testid="assistant-starter">
                        {prompt}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        <ol role="log" aria-label={labels.messagesLabel} aria-busy={busy} className="space-y-4" data-testid="assistant-log">
          {turns.map((turn) => (
            <li key={turn.id} className={cn("flex flex-col", turn.role === "user" ? "items-end" : "items-start")} data-testid={`turn-${turn.role}`}>
              <div
                className={cn(
                  "max-w-[85%] rounded-lg px-4 py-3",
                  turn.role === "user" ? "bg-primary-soft text-on-primary-soft" : "w-full max-w-full border border-border bg-surface sm:max-w-[85%]",
                )}
              >
                <p className="text-xs text-text-muted">{turn.role === "user" ? labels.you : labels.assistantName}</p>
                <p className="mt-1 whitespace-pre-wrap" dir="auto">{turn.content}</p>
                {turn.role === "assistant" ? (
                  <AssistantCards cards={turn.cards as AiCard[]} locale={locale} intlLocale={intlLocale} labels={cardLabels} vocab={vocab} />
                ) : null}
              </div>
            </li>
          ))}
          {pending ? (
            <li className="flex flex-col items-start" data-testid="assistant-pending">
              <div className="w-full rounded-lg border border-border bg-surface px-4 py-3 sm:max-w-[85%]">
                <p className="text-xs text-text-muted">{labels.assistantName}</p>
                {pending.text ? <p className="mt-1 whitespace-pre-wrap" dir="auto">{pending.text}</p> : null}
                {pending.status ? (
                  <p className="mt-1 flex items-center gap-2 text-sm text-text-muted">
                    <span className="inline-block size-2 animate-pulse rounded-full bg-primary motion-reduce:animate-none" aria-hidden="true" />
                    {pending.status}
                  </p>
                ) : null}
              </div>
            </li>
          ) : null}
        </ol>
        <div ref={endRef} />
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {announce}
      </p>

      {failure ? (
        <Alert tone={failure.fatal ? "info" : "warning"} role="alert" title={failure.fatal ? labels.error.unavailableTitle : undefined}>
          <p>{failure.message}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {failure.retry ? (
              <Button size="sm" variant="secondary" onClick={() => failure.retry && void send(failure.retry.content, failure.retry.key)} data-testid="assistant-retry">
                {labels.error.retry}
              </Button>
            ) : null}
            <Link href={handoffHref} className={buttonClass("ghost", "sm")}>
              {labels.talkToPerson}
            </Link>
          </div>
        </Alert>
      ) : null}

      <form onSubmit={onSubmit} className="flex flex-col gap-2" aria-label={labels.title} data-testid="assistant-form">
        <label htmlFor={inputId} className="sr-only">
          {labels.inputLabel}
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id={inputId}
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            maxLength={maxChars}
            placeholder={labels.placeholder}
            aria-describedby={hintId}
            disabled={disabled}
            dir="auto"
            className="min-h-12 flex-1 resize-y rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-60"
            data-testid="assistant-input"
          />
          <Button type="submit" disabled={disabled || busy || !draft.trim()} data-testid="assistant-send">
            {busy ? labels.sending : labels.send}
          </Button>
        </div>
        <p id={hintId} className="flex flex-wrap justify-between gap-2 text-xs text-text-muted">
          <span>{labels.sendHint}</span>
          <span className="hx-ltr-nums">{fill(labels.charCount, { count: draft.length, max: maxChars })}</span>
        </p>
      </form>

      <p className="text-xs text-text-muted" data-testid="assistant-notice">
        {labels.notice}
      </p>
    </div>
  );
}
