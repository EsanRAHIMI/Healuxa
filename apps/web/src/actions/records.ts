"use server";

import { unwrap } from "@healuxa/api-client";
import { refresh } from "next/cache";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";
import { DEFAULT_EXPIRY_DAYS, EXPIRY_CHOICES, ID_RE, PURPOSES } from "@/lib/records";

/** One dialog, one submit: share the chosen records with one provider or facility. */
export async function shareRecordsAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const recordIds = [...new Set(fd.getAll("record_ids").filter((v): v is string => typeof v === "string" && ID_RE.test(v)))];
    const [granteeType, granteeId] = str(fd, "grantee").split(":");
    const errors: Record<string, string> = {};
    if (!recordIds.length) errors.record_ids = t("records.pickRecord");
    if ((granteeType !== "provider" && granteeType !== "facility") || !granteeId || !ID_RE.test(granteeId)) errors.grantee = t("records.pickGrantee");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const days = Number(str(fd, "expires_in_days") || DEFAULT_EXPIRY_DAYS);
    const purpose = str(fd, "purpose") || "consultation";
    const appointmentId = str(fd, "appointment_id");
    const api = await userApi();
    await unwrap(
      api.profile.POST("/record-grants", {
        params: { header: { "Idempotency-Key": str(fd, "share_key") || undefined } },
        body: {
          grantee_type: granteeType as "provider" | "facility",
          grantee_id: granteeId!,
          record_ids: recordIds,
          purpose: (PURPOSES as readonly string[]).includes(purpose) ? (purpose as (typeof PURPOSES)[number]) : "consultation",
          expires_in_days: (EXPIRY_CHOICES as readonly number[]).includes(days) ? days : DEFAULT_EXPIRY_DAYS,
          ...(ID_RE.test(appointmentId) ? { appointment_id: appointmentId } : {}),
        },
      }),
    );
    refresh();
    return t("records.shared");
  });
}

/** One click: stop sharing (one record, or the whole grant when no record is named). */
export async function revokeShareAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const grantId = str(fd, "grant_id");
    const recordId = str(fd, "record_id");
    if (!ID_RE.test(grantId)) return invalid(locale, {});
    const api = await userApi();
    await unwrap(
      api.profile.POST("/record-grants/{grant_id}/revoke", {
        params: { path: { grant_id: grantId } },
        body: ID_RE.test(recordId) ? { record_ids: [recordId] } : {},
      }),
    );
    refresh();
    return getT(locale)("records.revoked");
  });
}

export async function deleteRecordAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const recordId = str(fd, "record_id");
    if (!ID_RE.test(recordId)) return invalid(locale, {});
    const api = await userApi();
    await unwrap(api.profile.DELETE("/records/{record_id}", { params: { path: { record_id: recordId } } }));
    refresh();
    return getT(locale)("records.deleted");
  });
}
