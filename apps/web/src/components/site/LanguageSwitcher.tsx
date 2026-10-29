"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface LanguageOption {
  code: string;
  nativeName: string;
  dir: "ltr" | "rtl";
}

/** Links to the same page in each launch locale. Plain links: works without JS, crawlable. */
export function LanguageSwitcher({ current, options, label }: { current: string; options: LanguageOption[]; label: string }) {
  const pathname = usePathname() ?? `/${current}`;
  const rest = pathname.replace(/^\/[a-z]{2}(?=\/|$)/, "");
  return (
    <nav aria-label={label}>
      <ul className="flex items-center gap-1 text-sm">
        {options.map((o) => (
          <li key={o.code}>
            <Link
              href={`/${o.code}${rest}`}
              hrefLang={o.code}
              lang={o.code}
              dir={o.dir}
              aria-current={o.code === current ? "true" : undefined}
              prefetch={false}
              className={
                "inline-flex min-h-9 items-center rounded-md px-2 no-underline " +
                (o.code === current ? "bg-primary-soft font-semibold text-on-primary-soft" : "text-text hover:bg-surface-muted")
              }
            >
              {o.nativeName}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
