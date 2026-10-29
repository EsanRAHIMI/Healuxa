export const CONSENT_KEYS = ["marketing_email", "marketing_sms", "analytics"] as const;
export type ConsentKey = (typeof CONSENT_KEYS)[number];

export const CONSENT_LABEL_KEYS: Record<ConsentKey, string> = {
  marketing_email: "consent.marketingEmail",
  marketing_sms: "consent.marketingSms",
  analytics: "consent.analytics",
};
