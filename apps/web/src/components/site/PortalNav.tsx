"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Section navigation for portals; marks the current page with aria-current. */
export function PortalNav({ label, items }: { label: string; items: { href: string; label: string; exact?: boolean }[] }) {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label={label} className="mb-8 border-b border-border">
      <ul className="flex gap-1 overflow-x-auto">
        {items.map((item) => {
          const current = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href} className="shrink-0">
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={
                  "inline-flex min-h-11 items-center border-b-2 px-3 text-sm no-underline " +
                  (current ? "border-primary font-semibold text-text" : "border-transparent text-text-muted hover:text-text")
                }
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
