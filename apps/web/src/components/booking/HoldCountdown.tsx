"use client";

import { useEffect, useState } from "react";

/** Remaining hold time (display only — appointment-service expires the hold server-side). */
export function HoldCountdown({ expiresAt, label, expiredLabel }: { expiresAt: string; label: string; expiredLabel: string }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (now === null) return null;
  const left = Math.max(0, Math.floor((Date.parse(expiresAt) - now) / 1000));
  if (left === 0) return <p className="font-medium text-danger">{expiredLabel}</p>;
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  return (
    <p className="font-medium">
      {label}{" "}
      <span className="hx-ltr-nums" role="timer" aria-live="off">
        {mm}:{ss}
      </span>
    </p>
  );
}
