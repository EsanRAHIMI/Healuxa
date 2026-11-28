"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useTransition, type FormEvent } from "react";

import { cn } from "@/components/ui/cn";
import { buttonClass } from "@/components/ui/primitives";

export interface UploadLabels {
  file: string;
  fileHint: string;
  docTitle: string;
  type: string;
  date: string;
  note: string;
  optional: string;
  submit: string;
  uploading: string;
  done: string;
  chooseFile: string;
  tooLarge: string;
  wrongType: string;
  failed: string;
  full: string;
  signIn: string;
}

const control =
  "block w-full min-h-11 rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text placeholder:text-text-muted aria-[invalid=true]:border-danger";
const ACCEPT = "application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png";

/**
 * One-screen upload. The file goes to the BFF route (/api/records), which streams it to profile-service;
 * the CSRF token travels in a header and must match the httpOnly cookie.
 */
export function UploadForm({
  csrf,
  maxBytes,
  types,
  labels,
}: {
  csrf: string;
  maxBytes: number;
  types: { value: string; label: string }[];
  labels: UploadLabels;
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<{ field?: string; message: string } | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [, startTransition] = useTransition();

  const onFile = (file: File | undefined) => {
    setDone(false);
    if (!file) return;
    if (file.size > maxBytes) setError({ field: "file", message: labels.tooLarge });
    else setError(null);
    const title = formRef.current?.elements.namedItem("title") as HTMLInputElement | null;
    if (title && !title.value) title.value = file.name.replace(/\.[^.]+$/, "").slice(0, 160);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const file = fd.get("file");
    if (!(file instanceof File) || file.size === 0) return setError({ field: "file", message: labels.chooseFile });
    if (file.size > maxBytes) return setError({ field: "file", message: labels.tooLarge });
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      const res = await fetch("/api/records", {
        method: "POST",
        body: fd,
        headers: { "x-csrf-token": csrf, "idempotency-key": `upl_${crypto.randomUUID()}` },
        credentials: "same-origin",
      });
      if (res.status === 201) {
        form.reset();
        setDone(true);
        startTransition(() => router.refresh());
        return;
      }
      const body = (await res.json().catch(() => ({}))) as { code?: string; errors?: { field?: string; code?: string }[] };
      const fieldError = body.errors?.[0];
      if (res.status === 401) setError({ message: labels.signIn });
      else if (res.status === 413 || fieldError?.code === "too_large") setError({ field: "file", message: labels.tooLarge });
      else if (fieldError?.code === "unsupported_type" || fieldError?.code === "type_mismatch") setError({ field: "file", message: labels.wrongType });
      else if (fieldError?.code === "record_limit" || fieldError?.code === "storage_limit") setError({ message: labels.full });
      else if (fieldError?.field && fieldError.field !== "file") setError({ field: fieldError.field, message: labels.failed });
      else setError({ message: labels.failed });
    } catch {
      setError({ message: labels.failed });
    } finally {
      setBusy(false);
    }
  };

  const invalid = (name: string) => (error?.field === name ? true : undefined);
  return (
    <form ref={formRef} onSubmit={onSubmit} noValidate aria-busy={busy} data-testid="record-upload-form" className="grid gap-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <label htmlFor="rec-file" className="mb-1.5 block text-sm font-medium">
          {labels.file}
        </label>
        <input
          id="rec-file"
          name="file"
          type="file"
          accept={ACCEPT}
          required
          aria-invalid={invalid("file")}
          aria-describedby="rec-file-hint"
          onChange={(e) => onFile(e.currentTarget.files?.[0])}
          className={cn(control, "py-1.5 file:me-3 file:rounded file:border-0 file:bg-surface-muted file:px-3 file:py-1.5")}
        />
        <p id="rec-file-hint" className="mt-1.5 text-sm text-text-muted">
          {labels.fileHint}
        </p>
      </div>
      <div>
        <label htmlFor="rec-title" className="mb-1.5 block text-sm font-medium">
          {labels.docTitle}
        </label>
        <input id="rec-title" name="title" required maxLength={160} aria-invalid={invalid("title")} className={control} />
      </div>
      <div>
        <label htmlFor="rec-type" className="mb-1.5 block text-sm font-medium">
          {labels.type}
        </label>
        <select id="rec-type" name="type" defaultValue="lab_result" className={control}>
          {types.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="rec-date" className="mb-1.5 block text-sm font-medium">
          {labels.date} <span className="font-normal text-text-muted">({labels.optional})</span>
        </label>
        <input id="rec-date" name="document_date" type="date" max={new Date().toISOString().slice(0, 10)} aria-invalid={invalid("document_date")} className={cn(control, "hx-ltr-nums")} />
      </div>
      <div>
        <label htmlFor="rec-note" className="mb-1.5 block text-sm font-medium">
          {labels.note} <span className="font-normal text-text-muted">({labels.optional})</span>
        </label>
        <input id="rec-note" name="note" maxLength={1000} className={control} />
      </div>
      <div className="flex flex-wrap items-center gap-3 md:col-span-2" aria-live="polite">
        <button type="submit" className={buttonClass("primary", "md")} disabled={busy} data-testid="record-upload-submit">
          {busy ? labels.uploading : labels.submit}
        </button>
        {error ? (
          <p role="alert" className="text-sm font-medium text-danger">
            {error.message}
          </p>
        ) : done ? (
          <p role="status" className="text-sm text-text-muted">
            {labels.done}
          </p>
        ) : null}
      </div>
    </form>
  );
}
