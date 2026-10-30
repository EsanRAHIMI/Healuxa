/**
 * Server-side configuration. Read lazily so `next build` works without runtime secrets; every
 * variable is documented in apps/web/.env.example.
 */
import "server-only";

function read(name: string, fallback?: string): string {
  const value = process.env[name];
  if (value !== undefined && value !== "") return value;
  if (fallback !== undefined) return fallback;
  throw new Error(`Missing required environment variable ${name}`);
}

function bool(name: string, fallback: boolean): boolean {
  const value = process.env[name];
  if (value === undefined || value === "") return fallback;
  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

export const env = {
  get siteUrl() {
    return read("SITE_URL", "http://localhost:3000").replace(/\/+$/, "");
  },
  get identityApiUrl() {
    return read("IDENTITY_API_URL", "http://127.0.0.1:8001/v1");
  },
  get providerApiUrl() {
    return read("PROVIDER_API_URL", "http://127.0.0.1:8005/v1");
  },
  get profileApiUrl() {
    return read("PROFILE_API_URL", "http://127.0.0.1:8002/v1");
  },
  get assessmentApiUrl() {
    return read("ASSESSMENT_API_URL", "http://127.0.0.1:8003/v1");
  },
  get appointmentApiUrl() {
    return read("APPOINTMENT_API_URL", "http://127.0.0.1:8007/v1");
  },
  get conciergeApiUrl() {
    return read("CONCIERGE_API_URL", "http://127.0.0.1:8021/v1");
  },
  get notificationApiUrl() {
    return read("NOTIFICATION_API_URL", "http://127.0.0.1:8022/v1");
  },
  get paymentApiUrl() {
    return read("PAYMENT_API_URL", "http://127.0.0.1:8010/v1");
  },
  get subscriptionApiUrl() {
    return read("SUBSCRIPTION_API_URL", "http://127.0.0.1:8009/v1");
  },
  /** JWKS of identity-service, used to verify access tokens locally (no service secret in the web tier). */
  get identityJwksUrl() {
    return read("IDENTITY_JWKS_URL", `${this.identityApiUrl.replace(/\/v1$/, "")}/.well-known/jwks.json`);
  },
  get jwtIssuer() {
    return read("IDENTITY_JWT_ISSUER", "https://api.healuxa.com");
  },
  /** Secure cookies (and __Host- prefix). Only disable for plain-http local E2E runs. */
  get cookieSecure() {
    return bool("AUTH_COOKIE_SECURE", process.env.NODE_ENV === "production");
  },
  /** Seconds public directory/catalog reads are cached in the Next data cache. */
  get publicRevalidateSeconds() {
    return Number(read("PUBLIC_REVALIDATE_SECONDS", "60"));
  },
  get apiTimeoutMs() {
    return Number(read("API_TIMEOUT_MS", "8000"));
  },
  get supportEmail() {
    return read("SUPPORT_EMAIL", "concierge@healuxa.com");
  },
  get supportPhone(): string | null {
    return process.env.SUPPORT_PHONE || null;
  },
  get supportWhatsapp(): string | null {
    return process.env.SUPPORT_WHATSAPP || null;
  },
  get trustForwardedFor() {
    return bool("TRUST_PROXY_HEADERS", true);
  },
};
