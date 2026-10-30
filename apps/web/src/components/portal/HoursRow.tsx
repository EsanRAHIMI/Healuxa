"use client";

import { useState } from "react";

import { useFormCtx } from "@/components/forms/ActionForm";

const input = "min-h-11 rounded-md border border-border-strong bg-surface px-2 text-base aria-[invalid=true]:border-danger";

/** One weekday in the hours editor: open toggle + one or two windows (field names match replaceHoursAction). */
export function HoursRow({
  day,
  dayLabel,
  open: initialOpen,
  first,
  second,
  labels,
}: {
  day: number;
  dayLabel: string;
  open: boolean;
  first: { start: string; end: string };
  second?: { start: string; end: string };
  labels: { open: string; from: string; to: string; split: string };
}) {
  const [open, setOpen] = useState(initialOpen);
  const [split, setSplit] = useState(!!second);
  const { state } = useFormCtx();
  const err = (name: string) => state.fieldErrors?.[name];
  const end = (v: string) => (v === "24:00" ? "00:00" : v);
  return (
    <fieldset className="rounded-md border border-border p-3">
      <legend className="px-1 font-medium">{dayLabel}</legend>
      <label className="flex min-h-11 items-center gap-2">
        <input type="checkbox" name={`open_${day}`} checked={open} onChange={(e) => setOpen(e.target.checked)} className="size-5 accent-[var(--hx-color-primary)]" />
        {labels.open}
      </label>
      {open ? (
        <div className="mt-2 space-y-2">
          {[0, ...(split ? [1] : [])].map((i) => {
            const suffix = i === 0 ? "" : "2";
            const w = i === 0 ? first : (second ?? { start: "16:00", end: "20:00" });
            const errorText = err(`end${suffix}_${day}`);
            return (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2 text-sm">
                  {labels.from}
                  <input type="time" name={`start${suffix}_${day}`} defaultValue={w.start} className={input} step={300} aria-invalid={errorText ? true : undefined} />
                </label>
                <label className="flex items-center gap-2 text-sm">
                  {labels.to}
                  <input type="time" name={`end${suffix}_${day}`} defaultValue={end(w.end)} className={input} step={300} aria-invalid={errorText ? true : undefined} />
                </label>
                {errorText ? <span className="text-sm text-danger">{errorText}</span> : null}
              </div>
            );
          })}
          <label className="flex min-h-9 items-center gap-2 text-sm text-text-muted">
            <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} className="size-4 accent-[var(--hx-color-primary)]" />
            {labels.split}
          </label>
        </div>
      ) : null}
    </fieldset>
  );
}
