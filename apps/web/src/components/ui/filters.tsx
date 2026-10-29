import Link from "next/link";
import type { ReactNode } from "react";

import { buttonClass } from "./primitives";

const control = "block w-full min-h-11 rounded-md border border-border-strong bg-surface px-3 py-2 text-base text-text";

/** GET filter controls (no JS required; results are shareable URLs). */
export function FilterInput({ name, label, defaultValue, placeholder, id, inputMode }: { name: string; label: string; defaultValue?: string; placeholder?: string; id?: string; inputMode?: "text" | "decimal" | "numeric" }) {
  const fid = id ?? `filter-${name}`;
  return (
    <div>
      <label htmlFor={fid} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <input id={fid} name={name} defaultValue={defaultValue} placeholder={placeholder} inputMode={inputMode} className={control} />
    </div>
  );
}

export function FilterSelect({ name, label, defaultValue, options, anyLabel }: { name: string; label: string; defaultValue?: string; options: { value: string; label: string }[]; anyLabel: string }) {
  const fid = `filter-${name}`;
  return (
    <div>
      <label htmlFor={fid} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <select id={fid} name={name} defaultValue={defaultValue ?? ""} className={control}>
        <option value="">{anyLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function FilterBar({ action, label, children, submitLabel, clearHref, clearLabel }: { action: string; label: string; children: ReactNode; submitLabel: string; clearHref: string; clearLabel: string }) {
  return (
    <form method="get" action={action} role="search" aria-label={label} className="rounded-lg border border-border bg-surface p-4 md:p-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="submit" className={buttonClass("primary", "md")}>
          {submitLabel}
        </button>
        <Link href={clearHref} className={buttonClass("ghost", "md")}>
          {clearLabel}
        </Link>
      </div>
    </form>
  );
}

/** Forward-only cursor pagination (the APIs are cursor based). */
export function CursorPager({ basePath, params, nextCursor, isFirst, nextLabel, firstLabel, navLabel }: { basePath: string; params: Record<string, string | undefined>; nextCursor: string | null | undefined; isFirst: boolean; nextLabel: string; firstLabel: string; navLabel: string }) {
  if (!nextCursor && isFirst) return null;
  const qs = (extra: Record<string, string | undefined>) => {
    const u = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params, ...extra })) if (v) u.set(k, v);
    const s = u.toString();
    return s ? `${basePath}?${s}` : basePath;
  };
  return (
    <nav aria-label={navLabel} className="mt-8 flex flex-wrap gap-3">
      {!isFirst ? (
        <Link href={qs({ cursor: undefined })} className={buttonClass("secondary", "md")}>
          {firstLabel}
        </Link>
      ) : null}
      {nextCursor ? (
        <Link href={qs({ cursor: nextCursor })} className={buttonClass("secondary", "md")} rel="next">
          {nextLabel}
        </Link>
      ) : null}
    </nav>
  );
}
