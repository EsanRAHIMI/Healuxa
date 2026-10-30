"use server";

/**
 * Staff decisions. Permission checks happen in the services (providers:verify, facilities:verify,
 * payments:refund…); the UI only additionally requires a written note for every decision.
 */
import { idempotencyHeader, unwrap, type ProviderStatus } from "@healuxa/api-client";
import { revalidatePath } from "next/cache";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { str, toMinorUnits, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

function note(fd: FormData, locale: Parameters<typeof getT>[0]) {
  const n = str(fd, "note");
  return n.length >= 3 && n.length <= 1000 ? n : invalid(locale, { note: getT(locale)("admin.errNote") });
}

export async function reviewCredentialAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const decision = str(fd, "decision");
    if (decision !== "verify" && decision !== "reject") return invalid(locale, { decision: "invalid" });
    const n = note(fd, locale);
    if (typeof n !== "string") return n;
    const api = await userApi();
    await unwrap(
      api.provider.POST("/providers/{id}/credentials/{credential_id}/review", {
        params: { path: { id: str(fd, "provider_id"), credential_id: str(fd, "credential_id") } },
        body: { decision, note: n },
      }),
    );
    revalidatePath(`/${locale}/admin`, "layout");
    return getT(locale)(decision === "verify" ? "admin.credentialVerified" : "admin.credentialRejected");
  }, (locale) => ({ conflict: getT(locale)("admin.alreadyReviewed") }));
}

export async function reviewFacilityAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const decision = str(fd, "decision");
    if (decision !== "verify" && decision !== "reject") return invalid(locale, { decision: "invalid" });
    const n = note(fd, locale);
    if (typeof n !== "string") return n;
    const api = await userApi();
    await unwrap(api.provider.POST("/facilities/{facility_id}/review", { params: { path: { facility_id: str(fd, "facility_id") } }, body: { decision, note: n } }));
    revalidatePath(`/${locale}/admin`, "layout");
    return getT(locale)(decision === "verify" ? "admin.facilityVerified" : "admin.facilityRejected");
  }, (locale) => ({ conflict: getT(locale)("admin.alreadyReviewed") }));
}

export async function changeProviderStatusAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const status = str(fd, "status") as ProviderStatus;
    if (!["pending", "active", "suspended", "offboarded"].includes(status)) return invalid(locale, { status: "invalid" });
    const reason = str(fd, "reason");
    if (reason.length < 3) return invalid(locale, { reason: getT(locale)("admin.errNote") });
    const api = await userApi();
    await unwrap(api.provider.POST("/providers/{id}/status", { params: { path: { id: str(fd, "provider_id") } }, body: { status, reason: reason.slice(0, 1000) } }));
    revalidatePath(`/${locale}/admin`, "layout");
    return getT(locale)("admin.statusChanged");
  });
}

export async function refundAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const reason = str(fd, "reason");
    const reasons = ["requested_by_customer", "appointment_cancelled", "provider_declined", "duplicate", "fraudulent", "service_issue", "goodwill"];
    if (!reasons.includes(reason)) return invalid(locale, { reason: t("admin.errReason") });
    const amountRaw = str(fd, "amount");
    const amount = amountRaw ? toMinorUnits(amountRaw) : undefined;
    if (amount !== undefined && (Number.isNaN(amount) || amount < 1)) return invalid(locale, { amount: t("pp.errAmount") });
    const n = note(fd, locale);
    if (typeof n !== "string") return n;
    const api = await userApi();
    await unwrap(
      api.payment.POST("/payments/{id}/refunds", {
        params: { path: { id: str(fd, "payment_id") }, header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
        body: { reason: reason as "goodwill", note: n.slice(0, 500), ...(amount !== undefined ? { amount_minor: amount } : {}), apply_policy: fd.get("apply_policy") === "on" },
      }),
    );
    revalidatePath(`/${locale}/admin/payments`, "layout");
    return t("admin.refundRequested");
  });
}

export async function capturePaymentAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    const id = str(fd, "payment_id");
    const op = str(fd, "op");
    if (op === "capture") await unwrap(api.payment.POST("/payments/{id}/capture", { params: { path: { id } } }));
    else if (op === "cancel") await unwrap(api.payment.POST("/payments/{id}/cancel", { params: { path: { id } } }));
    else return invalid(locale, { op: "invalid" });
    revalidatePath(`/${locale}/admin/payments`, "layout");
    return getT(locale)("admin.paymentUpdated");
  });
}
