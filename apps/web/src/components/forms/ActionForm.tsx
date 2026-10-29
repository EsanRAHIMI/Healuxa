"use client";

import { createContext, startTransition, useActionState, useContext, useEffect, useRef, type FormEvent, type ReactNode } from "react";

import { Alert } from "@/components/ui/primitives";
import { initialFormState, type FormState } from "@/lib/forms";

interface Ctx {
  state: FormState;
  pending: boolean;
}

const FormCtx = createContext<Ctx>({ state: initialFormState, pending: false });

export function useFormCtx(): Ctx {
  return useContext(FormCtx);
}

export interface ActionFormProps {
  action: (prev: FormState, fd: FormData) => Promise<FormState>;
  csrf: string;
  locale: string;
  children: ReactNode;
  className?: string;
  /** Accessible name for the form landmark. */
  label?: string;
  /** Labels for the message details (already translated). */
  detailLabel?: string;
  referenceLabel?: string;
  /** Show the success message (default) — off when the action redirects. */
  showSuccess?: boolean;
  /** Reset fields after success (create forms). */
  resetOnSuccess?: boolean;
  hidden?: Record<string, string>;
  testId?: string;
}

/**
 * Progressive-enhancement form around a Server Action. Without JS it posts natively; with JS it
 * dispatches in a transition so field values survive validation errors (React would otherwise
 * reset the form). Status is announced via a polite/assertive live region.
 */
export function ActionForm({
  action,
  csrf,
  locale,
  children,
  className,
  label,
  detailLabel = "Details",
  referenceLabel = "Reference",
  showSuccess = true,
  resetOnSuccess = false,
  hidden,
  testId,
}: ActionFormProps) {
  const [state, formAction, pending] = useActionState(action, initialFormState);
  const ref = useRef<HTMLFormElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state.ok === false) {
      const firstInvalid = ref.current?.querySelector<HTMLElement>("[aria-invalid='true']");
      (firstInvalid ?? statusRef.current)?.focus();
    }
    if (state.ok && resetOnSuccess) ref.current?.reset();
  }, [state, resetOnSuccess]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fd = new FormData(event.currentTarget, (event.nativeEvent as SubmitEvent).submitter);
    startTransition(() => formAction(fd));
  };

  return (
    <FormCtx.Provider value={{ state, pending }}>
      <form ref={ref} action={formAction} onSubmit={onSubmit} className={className} aria-label={label} noValidate data-testid={testId} aria-busy={pending}>
        <input type="hidden" name="_csrf" value={csrf} />
        <input type="hidden" name="_locale" value={locale} />
        {hidden ? Object.entries(hidden).map(([k, v]) => <input key={k} type="hidden" name={k} value={v} />) : null}
        {children}
        <div ref={statusRef} tabIndex={-1} className="mt-4 outline-none empty:hidden" aria-live={state.ok === false ? "assertive" : "polite"}>
          {state.ok === false && state.message ? (
            <Alert tone="danger" role="alert" title={state.message}>
              {state.detail ? (
                <p>
                  {detailLabel}: <span lang="en">{state.detail}</span>
                </p>
              ) : null}
              {state.traceId ? (
                <p className="text-xs opacity-80">
                  {referenceLabel}: <span className="hx-ltr-nums">{state.traceId}</span>
                </p>
              ) : null}
            </Alert>
          ) : null}
          {state.ok && showSuccess && state.message ? (
            <Alert tone="success" role="status" title={state.message} />
          ) : null}
        </div>
      </form>
    </FormCtx.Provider>
  );
}
