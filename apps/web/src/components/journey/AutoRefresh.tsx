"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Re-renders the current route a few times with growing delays. Used while an event-driven update
 * (intake assessment -> plan) is in flight; the server stops rendering this once the plan caught up.
 */
export function AutoRefresh({ delaysMs = [1500, 3000, 6000, 12000] }: { delaysMs?: number[] }) {
  const router = useRouter();
  useEffect(() => {
    const timers = delaysMs.map((ms) => setTimeout(() => router.refresh(), ms));
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- schedule once per mount
  }, []);
  return null;
}
