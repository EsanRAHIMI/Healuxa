"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * Keeps a server-rendered page current without a manual reload: re-fetches the route on an interval
 * while the tab is visible, and immediately when the tab regains focus or the network returns.
 * Server Components re-render with fresh backend data; client state (open dialogs, typed text) is kept.
 */
export function LiveRefresh({ intervalMs = 10000, label }: { intervalMs?: number; label?: string }) {
  const router = useRouter();
  const last = useRef(0);
  useEffect(() => {
    last.current = Date.now();
    const refresh = () => {
      if (document.visibilityState !== "visible" || !navigator.onLine) return;
      last.current = Date.now();
      router.refresh();
    };
    const onVisible = () => {
      // Coming back to the tab: refresh at once if the view is older than a few seconds.
      if (document.visibilityState === "visible" && Date.now() - last.current > 3000) refresh();
    };
    const timer = setInterval(refresh, intervalMs);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    window.addEventListener("online", refresh);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
      window.removeEventListener("online", refresh);
    };
  }, [router, intervalMs]);
  if (!label) return null;
  return (
    <span className="inline-flex items-center gap-2 text-sm text-text-muted" data-testid="live-indicator">
      <span className="relative flex size-2" aria-hidden="true">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-60 motion-reduce:hidden" />
        <span className="relative inline-flex size-2 rounded-full bg-success" />
      </span>
      {label}
    </span>
  );
}
