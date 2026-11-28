"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/components/ui/cn";

export interface NavItem {
  href: string;
  label: string;
  /** Match only this exact path (e.g. the account home, which prefixes every account page). */
  exact?: boolean;
  /** Other path prefixes that belong to this destination. */
  also?: string[];
}

function isCurrent(pathname: string, item: NavItem): boolean {
  if (item.exact) return pathname === item.href;
  return [item.href, ...(item.also ?? [])].some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Primary navigation row; the current destination is underlined and announced with aria-current. */
export function MainNav({ items, label }: { items: NavItem[]; label: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label={label}>
      <ul className="hx-container flex gap-1 overflow-x-auto text-sm md:gap-2">
        {items.map((item) => {
          const current = isCurrent(pathname, item);
          return (
            <li key={item.href} className="shrink-0">
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-11 items-center border-b-2 px-2.5 no-underline transition-colors",
                  current ? "border-primary font-semibold text-text" : "border-transparent text-text-muted hover:text-text",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Thumb-reach navigation for signed-in customers on small screens. */
export function BottomNav({ items, label }: { items: (NavItem & { icon: "home" | "journey" | "search" | "calendar" | "chat" })[]; label: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label={label} className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" data-testid="bottom-nav">
      <ul className="grid grid-cols-5">
        {items.map((item) => {
          const current = isCurrent(pathname, item);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={cn("flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[0.6875rem] leading-tight no-underline", current ? "font-semibold text-primary" : "text-text-muted")}
              >
                <Icon name={item.icon} />
                <span className="max-w-full truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const PATHS: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5Z",
  journey: "M5 19V6m0 0 4-2 6 3 4-2v10l-4 2-6-3-4 2",
  search: "M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14Zm5-2 5 5",
  calendar: "M4 6h16v14H4V6Zm0 4h16M8 3v4m8-4v4",
  chat: "M4 5h16v11H9l-5 4V5Z",
};

function Icon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
