import type { Locale } from "@healuxa/i18n";

import { Badge } from "@/components/ui/primitives";
import { getT } from "@/lib/i18n";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "primary";

const VERIFICATION_TONE: Record<string, Tone> = { verified: "success", under_review: "info", unverified: "neutral", rejected: "danger" };
const STATUS_TONE: Record<string, Tone> = {
  active: "success",
  pending: "warning",
  suspended: "danger",
  offboarded: "neutral",
  submitted: "info",
  verified: "success",
  rejected: "danger",
  expired: "warning",
  declined: "neutral",
  ended: "neutral",
  draft: "neutral",
  retired: "neutral",
  closed: "neutral",
};

export function VerificationBadge({ status, locale }: { status: string; locale: Locale }) {
  const t = getT(locale);
  return (
    <Badge tone={VERIFICATION_TONE[status] ?? "neutral"} data-testid="verification-status">
      {status === "verified" ? <CheckIcon /> : null}
      {t(`enums.verificationStatus.${status}`)}
    </Badge>
  );
}

/** `kind` selects the enum namespace: providerStatus, credentialStatus, affiliationStatus, offeringStatus, branchStatus. */
export function StatusBadge({ status, kind, locale }: { status: string; kind: string; locale: Locale }) {
  const t = getT(locale);
  return (
    <Badge tone={STATUS_TONE[status] ?? "neutral"} data-status={status}>
      {t(`enums.${kind}.${status}`)}
    </Badge>
  );
}

export function CheckIcon({ className = "size-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" clipRule="evenodd" />
    </svg>
  );
}
