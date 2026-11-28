"use client";

import { Dialog } from "radix-ui";
import { useEffect, useId, useState, type ReactNode } from "react";

import { ActionForm, useFormCtx } from "@/components/forms/ActionForm";
import { SubmitButton } from "@/components/forms/fields";
import { buttonClass } from "@/components/ui/primitives";
import type { FormState } from "@/lib/forms";

export interface GranteeOption {
  type: "provider" | "facility";
  id: string;
  name: string;
}

export interface ShareLabels {
  trigger: string;
  title: string;
  records: string;
  shareWith: string;
  careTeam: string;
  search: string;
  searchPlaceholder: string;
  searching: string;
  noMatches: string;
  noCareTeam: string;
  kindProvider: string;
  kindFacility: string;
  expiry: string;
  purpose: string;
  submit: string;
  sharing: string;
  cancel: string;
  close: string;
  detail: string;
  reference: string;
}

const control = "block w-full min-h-11 rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text";

function FieldError({ name }: { name: string }) {
  const { state } = useFormCtx();
  const error = state.fieldErrors?.[name];
  return error ? <p className="mt-1.5 text-sm font-medium text-danger">{error}</p> : null;
}

function CloseOnSuccess({ onDone }: { onDone: () => void }) {
  const { state } = useFormCtx();
  useEffect(() => {
    if (state.ok) {
      const timer = setTimeout(onDone, 600);
      return () => clearTimeout(timer);
    }
  }, [state, onDone]);
  return null;
}

/**
 * Share dialog: pick documents, who (bookings first, then name search), how long, why — one submit.
 */
export function ShareDialog({
  action,
  csrf,
  locale,
  records,
  preselected,
  candidates,
  defaultGrantee,
  appointmentId,
  expiryOptions,
  purposeOptions,
  labels,
  variant = "secondary",
  testId,
  children,
}: {
  action: (prev: FormState, fd: FormData) => Promise<FormState>;
  csrf: string;
  locale: string;
  records: { id: string; title: string; meta: string }[];
  preselected?: string[];
  candidates: GranteeOption[];
  defaultGrantee?: string;
  appointmentId?: string;
  expiryOptions: { value: string; label: string }[];
  purposeOptions: { value: string; label: string }[];
  labels: ShareLabels;
  variant?: "primary" | "secondary" | "ghost";
  testId?: string;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GranteeOption[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [shareKey, setShareKey] = useState("");
  const uid = useId();

  const onOpenChange = (next: boolean) => {
    // A fresh idempotency key per opening: retries of one submission never create two grants.
    if (next) setShareKey(`shr_${crypto.randomUUID()}`);
    setOpen(next);
  };

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`/api/records/grantees?q=${encodeURIComponent(q)}`, { signal: controller.signal, credentials: "same-origin" });
        const body = (await res.json()) as { data?: GranteeOption[] };
        setResults(body.data ?? []);
      } catch {
        /* aborted or offline: keep previous results */
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

  const shown = query.trim().length >= 2 ? results : null;
  const kind = (o: GranteeOption) => (o.type === "provider" ? labels.kindProvider : labels.kindFacility);
  const option = (o: GranteeOption, checked?: boolean) => (
    <li key={`${o.type}:${o.id}`}>
      <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface-muted">
        <input type="radio" name="grantee" value={`${o.type}:${o.id}`} defaultChecked={checked} className="size-5 accent-[var(--hx-color-primary)]" />
        <span className="font-medium">{o.name}</span>
        <span className="text-sm text-text-muted">{kind(o)}</span>
      </label>
    </li>
  );
  const pre = new Set(preselected ?? (records.length === 1 ? [records[0]!.id] : []));

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>
        <button type="button" className={buttonClass(variant, "sm")} data-testid={testId}>
          {children ?? labels.trigger}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-overlay" />
        <Dialog.Content className="fixed inset-x-4 top-[5vh] z-50 mx-auto max-h-[90vh] max-w-lg overflow-y-auto rounded-lg bg-surface-raised p-6 shadow-lg" data-testid="share-dialog">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-xl">{labels.title}</Dialog.Title>
            <Dialog.Close className={buttonClass("ghost", "sm")} aria-label={labels.close}>
              ×
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">{labels.title}</Dialog.Description>
          <ActionForm
            action={action}
            csrf={csrf}
            locale={locale}
            className="mt-4 space-y-5"
            label={labels.title}
            detailLabel={labels.detail}
            referenceLabel={labels.reference}
            hidden={{ share_key: shareKey, ...(appointmentId ? { appointment_id: appointmentId } : {}) }}
          >
            <CloseOnSuccess onDone={() => setOpen(false)} />
            <fieldset>
              <legend className="mb-2 text-sm font-medium">{labels.records}</legend>
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {records.map((r) => (
                  <li key={r.id}>
                    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface-muted">
                      <input type="checkbox" name="record_ids" value={r.id} defaultChecked={pre.has(r.id)} className="size-5 accent-[var(--hx-color-primary)]" />
                      <span className="font-medium">{r.title}</span>
                      <span className="text-sm text-text-muted">{r.meta}</span>
                    </label>
                  </li>
                ))}
              </ul>
              <FieldError name="record_ids" />
            </fieldset>
            <fieldset>
              <legend className="mb-2 text-sm font-medium">{labels.shareWith}</legend>
              {candidates.length ? (
                <>
                  <p className="mb-1 text-sm text-text-muted">{labels.careTeam}</p>
                  <ul className="space-y-1">{candidates.map((c) => option(c, defaultGrantee === `${c.type}:${c.id}` || candidates.length === 1))}</ul>
                </>
              ) : (
                <p className="text-sm text-text-muted">{labels.noCareTeam}</p>
              )}
              <div className="mt-3">
                <label htmlFor={`${uid}-q`} className="mb-1.5 block text-sm">
                  {labels.search}
                </label>
                <input id={`${uid}-q`} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={labels.searchPlaceholder} className={control} autoComplete="off" />
                <div aria-live="polite" className="mt-2">
                  {searching ? <p className="text-sm text-text-muted">{labels.searching}</p> : null}
                  {shown && !searching ? (
                    shown.filter((r) => !candidates.some((c) => c.id === r.id)).length ? (
                      <ul className="space-y-1">{shown.filter((r) => !candidates.some((c) => c.id === r.id)).map((r) => option(r))}</ul>
                    ) : (
                      <p className="text-sm text-text-muted">{labels.noMatches}</p>
                    )
                  ) : null}
                </div>
              </div>
              <FieldError name="grantee" />
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor={`${uid}-exp`} className="mb-1.5 block text-sm font-medium">
                  {labels.expiry}
                </label>
                <select id={`${uid}-exp`} name="expires_in_days" defaultValue="30" className={control}>
                  {expiryOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={`${uid}-purpose`} className="mb-1.5 block text-sm font-medium">
                  {labels.purpose}
                </label>
                <select id={`${uid}-purpose`} name="purpose" defaultValue="consultation" className={control}>
                  {purposeOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex flex-wrap justify-end gap-3">
              <Dialog.Close className={buttonClass("secondary", "md")} type="button">
                {labels.cancel}
              </Dialog.Close>
              <SubmitButton pendingLabel={labels.sharing} testId="share-submit">
                {labels.submit}
              </SubmitButton>
            </div>
          </ActionForm>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
