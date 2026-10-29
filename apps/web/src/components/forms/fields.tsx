"use client";

import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/components/ui/cn";
import { buttonClass } from "@/components/ui/primitives";

import { useFormCtx } from "./ActionForm";

const control =
  "block w-full min-h-11 rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text placeholder:text-text-muted " +
  "aria-[invalid=true]:border-danger disabled:opacity-60";

interface FieldBase {
  name: string;
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  requiredLabel?: string;
  optionalLabel?: string;
  className?: string;
  id?: string;
}

function useFieldA11y(name: string, id: string | undefined, hint: ReactNode | undefined) {
  const { state } = useFormCtx();
  const fieldId = id ?? `f-${name}`;
  const error = state.fieldErrors?.[name];
  const describedBy = [hint ? `${fieldId}-hint` : null, error ? `${fieldId}-error` : null].filter(Boolean).join(" ") || undefined;
  return { fieldId, error, describedBy };
}

function Label({ htmlFor, label, required, requiredLabel, optionalLabel }: { htmlFor: string; label: ReactNode; required?: boolean; requiredLabel?: string; optionalLabel?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium">
      {label}
      {required ? (
        <span className="text-danger" aria-hidden="true">
          {" "}
          *
        </span>
      ) : optionalLabel ? (
        <span className="font-normal text-text-muted"> ({optionalLabel})</span>
      ) : null}
      {required && requiredLabel ? <span className="sr-only"> ({requiredLabel})</span> : null}
    </label>
  );
}

function Messages({ fieldId, hint, error }: { fieldId: string; hint?: ReactNode; error?: string }) {
  return (
    <>
      {hint ? (
        <p id={`${fieldId}-hint`} className="mt-1.5 text-sm text-text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${fieldId}-error`} className="mt-1.5 text-sm font-medium text-danger">
          <span lang="en">{error}</span>
        </p>
      ) : null}
    </>
  );
}

export function TextField({
  name,
  label,
  hint,
  required,
  requiredLabel,
  optionalLabel,
  className,
  id,
  ...input
}: FieldBase & Omit<ComponentProps<"input">, "name" | "id" | "required">) {
  const { fieldId, error, describedBy } = useFieldA11y(name, id, hint);
  return (
    <div className={className}>
      <Label htmlFor={fieldId} label={label} required={required} requiredLabel={requiredLabel} optionalLabel={optionalLabel} />
      <input
        id={fieldId}
        name={name}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={control}
        {...input}
      />
      <Messages fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
}

export function TextArea({
  name,
  label,
  hint,
  required,
  requiredLabel,
  optionalLabel,
  className,
  id,
  ...input
}: FieldBase & Omit<ComponentProps<"textarea">, "name" | "id" | "required">) {
  const { fieldId, error, describedBy } = useFieldA11y(name, id, hint);
  return (
    <div className={className}>
      <Label htmlFor={fieldId} label={label} required={required} requiredLabel={requiredLabel} optionalLabel={optionalLabel} />
      <textarea
        id={fieldId}
        name={name}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(control, "min-h-24")}
        {...input}
      />
      <Messages fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
}

export function SelectField({
  name,
  label,
  hint,
  required,
  requiredLabel,
  optionalLabel,
  className,
  id,
  options,
  placeholder,
  ...select
}: FieldBase & Omit<ComponentProps<"select">, "name" | "id" | "required"> & { options: { value: string; label: string }[]; placeholder?: string }) {
  const { fieldId, error, describedBy } = useFieldA11y(name, id, hint);
  return (
    <div className={className}>
      <Label htmlFor={fieldId} label={label} required={required} requiredLabel={requiredLabel} optionalLabel={optionalLabel} />
      <select
        id={fieldId}
        name={name}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={control}
        {...select}
      >
        {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Messages fieldId={fieldId} hint={hint} error={error} />
    </div>
  );
}

export function CheckboxField({ name, label, hint, className, id, ...input }: Omit<FieldBase, "required"> & Omit<ComponentProps<"input">, "name" | "id" | "type">) {
  const { fieldId, error, describedBy } = useFieldA11y(name, id, hint);
  return (
    <div className={cn("flex gap-3", className)}>
      <input
        id={fieldId}
        type="checkbox"
        name={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className="mt-1 size-5 shrink-0 accent-[var(--hx-color-primary)]"
        {...input}
      />
      <div>
        <label htmlFor={fieldId} className="font-medium">
          {label}
        </label>
        <Messages fieldId={fieldId} hint={hint} error={error} />
      </div>
    </div>
  );
}

export function SubmitButton({
  children,
  pendingLabel,
  variant = "primary",
  className,
  name,
  value,
  testId,
}: {
  children: ReactNode;
  pendingLabel: string;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  className?: string;
  name?: string;
  value?: string;
  testId?: string;
}) {
  const { pending } = useFormCtx();
  return (
    <button type="submit" name={name} value={value} className={buttonClass(variant, "md", className)} aria-disabled={pending || undefined} disabled={pending} data-testid={testId}>
      {pending ? (
        <>
          <span className="size-4 animate-spin rounded-full border-2 border-current border-e-transparent" aria-hidden="true" />
          <span>{pendingLabel}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
