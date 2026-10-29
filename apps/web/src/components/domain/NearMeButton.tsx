"use client";

import { useState } from "react";

import { buttonClass } from "@/components/ui/primitives";

/** Fills the `near` input from the browser's geolocation (only on explicit click). */
export function NearMeButton({ targetId, label, busyLabel, deniedLabel }: { targetId: string; label: string; busyLabel: string; deniedLabel: string }) {
  const [state, setState] = useState<"idle" | "busy" | "denied">("idle");
  return (
    <div>
      <button
        type="button"
        className={buttonClass("secondary", "sm")}
        disabled={state === "busy"}
        onClick={() => {
          if (!("geolocation" in navigator)) return setState("denied");
          setState("busy");
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const input = document.getElementById(targetId) as HTMLInputElement | null;
              if (input) input.value = `${pos.coords.latitude.toFixed(4)},${pos.coords.longitude.toFixed(4)}`;
              setState("idle");
            },
            () => setState("denied"),
            { maximumAge: 600_000, timeout: 10_000 },
          );
        }}
      >
        {state === "busy" ? busyLabel : label}
      </button>
      <p role="status" className="mt-1 text-sm text-danger empty:hidden">
        {state === "denied" ? deniedLabel : ""}
      </p>
    </div>
  );
}
