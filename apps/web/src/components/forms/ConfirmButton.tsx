"use client";

import { AlertDialog } from "radix-ui";
import { useId, useState, type ReactNode } from "react";

import { buttonClass } from "@/components/ui/primitives";

import { useFormCtx } from "./ActionForm";

/**
 * Destructive/irreversible action guard: opens an accessible alert dialog (focus-trapped,
 * Escape to cancel) and only then submits the enclosing ActionForm.
 */
export function ConfirmButton({
  trigger,
  title,
  description,
  confirmLabel,
  cancelLabel,
  variant = "danger",
  name,
  value,
  testId,
}: {
  trigger: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  variant?: "danger" | "primary" | "secondary";
  name?: string;
  value?: string;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  const uid = useId();
  const { pending } = useFormCtx();
  return (
    <AlertDialog.Root open={open} onOpenChange={setOpen}>
      <AlertDialog.Trigger asChild>
        <button type="button" className={buttonClass(variant, "sm")} disabled={pending} data-testid={testId}>
          {trigger}
        </button>
      </AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-overlay" />
        <AlertDialog.Content className="fixed inset-x-4 top-1/2 z-50 mx-auto max-w-md -translate-y-1/2 rounded-lg bg-surface-raised p-6 shadow-lg">
          <AlertDialog.Title className="text-xl">{title}</AlertDialog.Title>
          {description ? <AlertDialog.Description className="mt-2 text-text-muted">{description}</AlertDialog.Description> : <AlertDialog.Description className="sr-only">{title}</AlertDialog.Description>}
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <AlertDialog.Cancel className={buttonClass("secondary", "md")}>{cancelLabel}</AlertDialog.Cancel>
            <button
              type="button"
              className={buttonClass(variant, "md")}
              data-testid={testId ? `${testId}-confirm` : undefined}
              onClick={(event) => {
                setOpen(false);
                const trigger = document.querySelector<HTMLButtonElement>(`[data-confirm-target="${CSS.escape(uid)}"]`);
                trigger?.click();
                event.preventDefault();
              }}
            >
              {confirmLabel}
            </button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
      {/* Hidden real submitter inside the form so name/value travel with the submission. */}
      <button type="submit" name={name} value={value} hidden data-confirm-target={uid} tabIndex={-1} aria-hidden="true" />
    </AlertDialog.Root>
  );
}
