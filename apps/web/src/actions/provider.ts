"use server";

import { idempotencyHeader, unwrap, type CredentialKind, type ProviderType, type ServiceOfferingPatch } from "@healuxa/api-client";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { list, optInt, optStr, str, toMinorUnits, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";
import { PROVIDER_TYPES } from "@/lib/query";
import { hhmmToMinutes, isValidTimeZone, zonedToUtcIso } from "@/lib/time";

const CREDENTIAL_KINDS: CredentialKind[] = ["professional_license", "board_certification", "malpractice_insurance", "other"];
const BIO_LOCALES = ["en", "ar", "fa"] as const;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function bioFrom(fd: FormData): Record<string, string> {
  const bio: Record<string, string> = {};
  for (const l of BIO_LOCALES) {
    const v = str(fd, `bio_${l}`);
    if (v) bio[l] = v.slice(0, 4000);
  }
  return bio;
}

function profileErrors(fd: FormData, t: (k: string) => string) {
  const errors: Record<string, string> = {};
  const name = str(fd, "display_name");
  if (name.length < 2 || name.length > 160) errors.display_name = t("pp.errDisplayName");
  if (list(fd, "specialties").length === 0) errors.specialties = t("pp.errSpecialties");
  if (fd.getAll("languages").length === 0) errors.languages = t("pp.errLanguages");
  return errors;
}

export async function applyProviderAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const type = str(fd, "type") as ProviderType;
    const errors = profileErrors(fd, t);
    if (!PROVIDER_TYPES.includes(type as (typeof PROVIDER_TYPES)[number])) errors.type = t("pp.errType");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(
      api.provider.POST("/providers", {
        params: { header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
        body: {
          type,
          display_name: str(fd, "display_name"),
          ...(optStr(fd, "title") ? { title: str(fd, "title") } : {}),
          bio: bioFrom(fd),
          specialties: list(fd, "specialties"),
          languages: fd.getAll("languages").map(String),
        },
      }),
    );
    refresh();
    target = `/${locale}/provider/credentials?applied=1`;
  }, (locale) => ({ conflict: getT(locale)("pp.alreadyApplied") }));
  if (state.ok && target) redirect(target);
  return state;
}

export async function updateProviderAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const errors = profileErrors(fd, t);
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(
      api.provider.PATCH("/providers/{id}", {
        params: { path: { id: str(fd, "provider_id") }, header: { "If-Match": str(fd, "etag") } },
        body: {
          display_name: str(fd, "display_name"),
          title: str(fd, "title"),
          bio: bioFrom(fd),
          specialties: list(fd, "specialties"),
          languages: fd.getAll("languages").map(String),
        },
      }),
    );
    refresh();
    return t("pp.profileSaved");
  }, (locale) => ({ conflict: getT(locale)("pp.editConflict") }));
}

export async function submitCredentialAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const kind = str(fd, "kind") as CredentialKind;
    const errors: Record<string, string> = {};
    if (!CREDENTIAL_KINDS.includes(kind)) errors.kind = t("pp.errKind");
    if (str(fd, "issuing_authority").length < 2) errors.issuing_authority = t("pp.errAuthority");
    if (str(fd, "number").length < 2) errors.number = t("pp.errNumber");
    const from = optStr(fd, "valid_from");
    const until = optStr(fd, "valid_until");
    if (from && !DATE.test(from)) errors.valid_from = t("pp.errDate");
    if (until && !DATE.test(until)) errors.valid_until = t("pp.errDate");
    if (from && until && until < from) errors.valid_until = t("pp.errDateOrder");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(
      api.provider.POST("/providers/{id}/credentials", {
        params: { path: { id: str(fd, "provider_id") } },
        body: {
          kind,
          issuing_authority: str(fd, "issuing_authority"),
          number: str(fd, "number"),
          ...(optStr(fd, "jurisdiction") ? { jurisdiction: str(fd, "jurisdiction") } : {}),
          ...(from ? { valid_from: from } : {}),
          ...(until ? { valid_until: until } : {}),
        },
      }),
    );
    refresh();
    return t("pp.credentialSubmitted");
  }, (locale) => ({ conflict: getT(locale)("pp.credentialDuplicate") }));
}

export async function requestAffiliationAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const branchId = str(fd, "branch_id");
    if (!branchId) return invalid(locale, { branch_id: t("pp.errBranch") });
    const api = await userApi();
    await unwrap(api.provider.POST("/affiliations", { body: { provider_id: str(fd, "provider_id"), branch_id: branchId } }));
    refresh();
    return t("pp.affiliationRequested");
  }, (locale) => ({ conflict: getT(locale)("pp.affiliationExists") }));
}

/** Shared by provider and facility portals. */
export async function decideAffiliationAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const decision = str(fd, "decision");
    if (decision !== "approve" && decision !== "decline" && decision !== "end") return invalid(locale, { decision: "invalid" });
    const api = await userApi();
    await unwrap(api.provider.POST("/affiliations/{affiliation_id}/decision", { params: { path: { affiliation_id: str(fd, "affiliation_id") } }, body: { decision } }));
    refresh();
    return getT(locale)({ approve: "pp.affiliationApproved", decline: "pp.affiliationDeclined", end: "pp.affiliationEnded" }[decision]);
  });
}

function offeringFields(fd: FormData, t: (k: string) => string) {
  const errors: Record<string, string> = {};
  const priceType = str(fd, "price_type");
  if (!["fixed", "from", "on_request"].includes(priceType)) errors.price_type = t("pp.errPriceType");
  const duration = optInt(fd, "duration_minutes");
  if (duration === undefined || Number.isNaN(duration) || duration < 5 || duration > 720) errors.duration_minutes = t("pp.errDuration");
  const buffer = optInt(fd, "buffer_minutes") ?? 0;
  if (Number.isNaN(buffer) || buffer < 0 || buffer > 240) errors.buffer_minutes = t("pp.errBuffer");
  let professional: number | undefined;
  let facility: number | undefined;
  if (priceType !== "on_request") {
    professional = toMinorUnits(str(fd, "professional_fee"));
    if (Number.isNaN(professional)) errors.professional_fee = t("pp.errAmount");
    const facilityRaw = str(fd, "facility_fee");
    facility = facilityRaw ? toMinorUnits(facilityRaw) : 0;
    if (Number.isNaN(facility)) errors.facility_fee = t("pp.errAmount");
  }
  return { errors, priceType: priceType as "fixed" | "from" | "on_request", duration: duration ?? 0, buffer, professional, facility };
}

export async function createOfferingAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    // Facility portal submits "providerId|branchId" for an active affiliation.
    const practice = str(fd, "practice");
    if (practice) {
      const [pid = "", bid = ""] = practice.split("|");
      fd.set("provider_id", pid);
      fd.set("branch_id", bid);
    }
    const f = offeringFields(fd, t);
    if (str(fd, "name").length < 2) f.errors.name = t("pp.errOfferingName");
    if (str(fd, "category").length < 2) f.errors.category = t("pp.errCategory");
    if (!str(fd, "branch_id") || !str(fd, "provider_id")) f.errors[practice !== "" || fd.has("practice") ? "practice" : "branch_id"] = t("pp.errBranch");
    if (Object.keys(f.errors).length) return invalid(locale, f.errors);
    const description = str(fd, "description");
    const api = await userApi();
    await unwrap(
      api.provider.POST("/providers/{id}/services", {
        params: { path: { id: str(fd, "provider_id") } },
        body: {
          branch_id: str(fd, "branch_id"),
          category: str(fd, "category"),
          name: str(fd, "name"),
          ...(description ? { description: { [locale]: description } } : {}),
          duration_minutes: f.duration,
          buffer_minutes: f.buffer,
          mode: str(fd, "mode") === "home_visit" ? "home_visit" : "in_person",
          price_type: f.priceType,
          ...(f.priceType !== "on_request" ? { professional_fee_minor: f.professional, facility_fee_minor: f.facility } : {}),
          currency: "AED",
        },
      }),
    );
    refresh();
    return t("pp.offeringCreated");
  });
}

export async function updateOfferingAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const f = offeringFields(fd, t);
    if (str(fd, "name").length < 2) f.errors.name = t("pp.errOfferingName");
    const status = str(fd, "status");
    if (!["draft", "active", "retired"].includes(status)) f.errors.status = t("pp.errStatus");
    if (Object.keys(f.errors).length) return invalid(locale, f.errors);
    const body: ServiceOfferingPatch = {
      name: str(fd, "name"),
      duration_minutes: f.duration,
      buffer_minutes: f.buffer,
      price_type: f.priceType,
      status: status as "draft" | "active" | "retired",
      ...(f.priceType !== "on_request" ? { professional_fee_minor: f.professional, facility_fee_minor: f.facility } : {}),
    };
    const api = await userApi();
    await unwrap(api.provider.PATCH("/services/{service_id}", { params: { path: { service_id: str(fd, "service_id") } }, body }));
    refresh();
    return t("pp.offeringSaved");
  });
}

export async function createRuleAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const errors: Record<string, string> = {};
    const weekdays = fd.getAll("weekday").map(Number).filter((d) => Number.isInteger(d) && d >= 0 && d <= 6);
    const start = str(fd, "start");
    const end = str(fd, "end");
    const from = str(fd, "effective_from");
    const until = optStr(fd, "effective_until");
    if (!str(fd, "branch_id")) errors.branch_id = t("pp.errBranch");
    if (weekdays.length === 0) errors.weekday = t("pp.errWeekday");
    if (Number.isNaN(hhmmToMinutes(start))) errors.start = t("pp.errTime");
    if (Number.isNaN(hhmmToMinutes(end, true))) errors.end = t("pp.errTime");
    else if (hhmmToMinutes(end, true) <= hhmmToMinutes(start)) errors.end = t("pp.errTimeOrder");
    if (!DATE.test(from)) errors.effective_from = t("pp.errDate");
    if (until && (!DATE.test(until) || until < from)) errors.effective_until = t("pp.errDateOrder");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    // One rule per weekday (the API models a single weekday per rule).
    for (const weekday of weekdays) {
      await unwrap(
        api.provider.POST("/providers/{id}/availability-rules", {
          params: { path: { id: str(fd, "provider_id") } },
          body: { branch_id: str(fd, "branch_id"), weekday, start, end, effective_from: from, ...(until ? { effective_until: until } : {}) },
        }),
      );
    }
    refresh();
    return t("pp.ruleCreated", { count: weekdays.length });
  }, (locale) => ({ conflict: getT(locale)("pp.ruleOverlap"), unprocessable: getT(locale)("pp.ruleOutsideHours") }));
}

export async function deleteRuleAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    await unwrap(api.provider.DELETE("/availability-rules/{rule_id}", { params: { path: { rule_id: str(fd, "rule_id") } } }));
    refresh();
    return getT(locale)("pp.ruleDeleted");
  });
}

export async function createExceptionAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const errors: Record<string, string> = {};
    const tz = str(fd, "timezone");
    const reason = str(fd, "reason");
    if (!isValidTimeZone(tz)) errors.timezone = t("pp.errTimezone");
    if (!["leave", "public_holiday", "training", "other"].includes(reason)) errors.reason = t("pp.errReason");
    const sd = str(fd, "start_date");
    const ed = str(fd, "end_date");
    const st = str(fd, "start_time") || "00:00";
    const et = str(fd, "end_time") || "23:59";
    if (!DATE.test(sd)) errors.start_date = t("pp.errDate");
    if (!DATE.test(ed)) errors.end_date = t("pp.errDate");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const startsAt = zonedToUtcIso(sd, st, tz);
    const endsAt = zonedToUtcIso(ed, et, tz);
    if (endsAt <= startsAt) return invalid(locale, { end_date: t("pp.errDateOrder") });
    const branchId = optStr(fd, "branch_id");
    const api = await userApi();
    await unwrap(
      api.provider.POST("/providers/{id}/availability-exceptions", {
        params: { path: { id: str(fd, "provider_id") } },
        body: { starts_at: startsAt, ends_at: endsAt, reason: reason as "leave", ...(branchId ? { branch_id: branchId } : {}) },
      }),
    );
    refresh();
    return t("pp.exceptionCreated");
  });
}
