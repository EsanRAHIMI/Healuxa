import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/components/ui/cn";

/** A figure with its label, set on a ruled row rather than boxed: reads as a report, not a card grid. */
export function Stat({ label, value, hint, tone }: { label: ReactNode; value: ReactNode; hint?: ReactNode; tone?: "default" | "attention" }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 md:border-s md:border-border md:ps-4 md:first:border-s-0 md:first:ps-0">
      <dt className="text-sm text-text-muted">{label}</dt>
      <dd className={cn("hx-ltr-nums font-serif text-3xl leading-none font-medium md:text-4xl", tone === "attention" && "text-primary")}>{value}</dd>
      {hint ? <dd className="text-sm text-text-muted">{hint}</dd> : null}
    </div>
  );
}

export function StatRow({ children, className }: { children: ReactNode; className?: string }) {
  return <dl className={cn("grid grid-cols-2 gap-x-4 gap-y-6 md:grid-flow-col md:auto-cols-fr md:grid-cols-none", className)}>{children}</dl>;
}

/** Section with a plain heading and an optional "view all" link on the trailing edge. */
export function Panel({ title, href, linkLabel, children, id, className }: { title: ReactNode; href?: string; linkLabel?: string; children: ReactNode; id: string; className?: string }) {
  return (
    <section aria-labelledby={`${id}-title`} className={cn("rounded-xl border border-border bg-surface p-5 md:p-6", className)}>
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 id={`${id}-title`} className="text-xl">
          {title}
        </h2>
        {href && linkLabel ? (
          <Link href={href} className="shrink-0 text-sm font-medium">
            {linkLabel}
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

/** Proportional bar for a status breakdown; segments carry their own labels in the legend below it. */
export function Breakdown({ items, total, emptyLabel }: { items: { key: string; label: string; count: number; className: string }[]; total: number; emptyLabel: string }) {
  if (total === 0) return <p className="text-sm text-text-muted">{emptyLabel}</p>;
  const shown = items.filter((i) => i.count > 0);
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
        {shown.map((i) => (
          <span key={i.key} className={i.className} style={{ inlineSize: `${(i.count / total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {shown.map((i) => (
          <li key={i.key} className="flex items-center gap-2">
            <span className={cn("size-2.5 rounded-full", i.className)} aria-hidden="true" />
            <span className="text-text-muted">{i.label}</span>
            <span className="hx-ltr-nums font-medium">{i.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The journey as a rail of stages; the current stage is the only filled node. */
export function JourneyRail({ stages }: { stages: { key: string; label: string; status: "pending" | "in_progress" | "completed" }[] }) {
  return (
    <ol className="flex w-full items-start" data-testid="journey-rail">
      {stages.map((s, i) => (
        <li key={s.key} className="relative flex min-w-0 flex-1 flex-col items-center gap-2 text-center" aria-current={s.status === "in_progress" ? "step" : undefined}>
          {i > 0 ? (
            <span aria-hidden="true" className={cn("absolute end-1/2 top-[0.6875rem] h-0.5 w-full -translate-y-1/2", s.status === "pending" ? "bg-current opacity-25" : "bg-current opacity-80")} />
          ) : null}
          <span
            aria-hidden="true"
            className={cn(
              "relative z-10 flex size-[1.375rem] items-center justify-center rounded-full border-2 border-current text-xs",
              s.status === "completed" && "bg-current",
              s.status === "in_progress" && "bg-current ring-4 ring-current/25",
              s.status === "pending" && "bg-[var(--rail-bg,var(--hx-color-surface))] opacity-60",
            )}
          />
          <span className={cn("px-1 text-xs leading-tight md:text-sm", s.status === "pending" && "opacity-70", s.status === "in_progress" && "font-semibold")}>{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
