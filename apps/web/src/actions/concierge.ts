"use server";

/**
 * Concierge-service mutations for customers (create case, select option, secure messages) and
 * coordinators (claim/assign, transitions, escalation, internal notes, provider options).
 * Data minimisation: no clinical fields anywhere; `needs_note` is logistics-only.
 */
import { unwrap, type ConciergeCaseCategory, type ConciergeCaseStatus } from "@healuxa/api-client";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { optStr, str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";

const CATEGORIES: ConciergeCaseCategory[] = ["medical_travel", "specialist_search", "second_opinion_coordination", "logistics", "other"];
const STATUSES: ConciergeCaseStatus[] = ["submitted", "triaged", "assigned", "in_progress", "awaiting_customer", "arranged", "completed", "cancelled", "escalated"];
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export async function createCaseAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const category = str(fd, "category") as ConciergeCaseCategory;
    const errors: Record<string, string> = {};
    if (!CATEGORIES.includes(category)) errors.category = t("concierge.errCategory");
    const start = optStr(fd, "preferred_start_date");
    const end = optStr(fd, "preferred_end_date");
    if (start && !DATE.test(start)) errors.preferred_start_date = t("pp.errDate");
    if (end && (!DATE.test(end) || (start && end < start))) errors.preferred_end_date = t("pp.errDateOrder");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    const created = await unwrap(
      api.concierge.POST("/concierge/cases", {
        body: {
          category,
          preferred_start_date: start ?? null,
          preferred_end_date: end ?? null,
          languages: fd.getAll("languages").map(String).slice(0, 5),
          destination_city: optStr(fd, "destination_city") ?? null,
          needs_note: optStr(fd, "needs_note")?.slice(0, 2000) ?? null,
        },
      }),
    );
    target = `/${locale}/account/concierge/${created.id}?created=1`;
  });
  if (state.ok && target) redirect(target);
  return state;
}

export async function postMessageAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const body = str(fd, "body");
    if (!body) return invalid(locale, { body: getT(locale)("concierge.errMessage") });
    const api = await userApi();
    await unwrap(api.concierge.POST("/concierge/cases/{id}/messages", { params: { path: { id: str(fd, "case_id") } }, body: { body: body.slice(0, 4000) } }));
    refresh();
    return { ok: true, at: Date.now() };
  });
}

export async function selectOptionAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    await unwrap(api.concierge.POST("/concierge/cases/{id}/options/{option_id}/select", { params: { path: { id: str(fd, "case_id"), option_id: str(fd, "option_id") } } }));
    refresh();
    return getT(locale)("concierge.optionSelected");
  });
}

export async function transitionCaseAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const to = str(fd, "to_status") as ConciergeCaseStatus;
    if (!STATUSES.includes(to)) return invalid(locale, { to_status: getT(locale)("concierge.errStatus") });
    const api = await userApi();
    await unwrap(
      api.concierge.POST("/concierge/cases/{id}/transitions", { params: { path: { id: str(fd, "case_id") } }, body: { to_status: to, reason: optStr(fd, "reason")?.slice(0, 500) ?? null } }),
    );
    refresh();
    return getT(locale)("concierge.statusChanged");
  }, (locale) => ({ conflict: getT(locale)("concierge.illegalTransition") }));
}

export async function assignCaseAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    const coordinator = optStr(fd, "coordinator_id");
    await unwrap(api.concierge.POST("/concierge/cases/{id}/assignment", { params: { path: { id: str(fd, "case_id") } }, body: coordinator ? { coordinator_id: coordinator } : {} }));
    refresh();
    return getT(locale)("concierge.assigned");
  });
}

export async function escalateCaseAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const reason = str(fd, "reason");
    if (reason.length < 3) return invalid(locale, { reason: getT(locale)("admin.errNote") });
    const api = await userApi();
    await unwrap(api.concierge.POST("/concierge/cases/{id}/escalation", { params: { path: { id: str(fd, "case_id") } }, body: { reason: reason.slice(0, 500) } }));
    refresh();
    return getT(locale)("concierge.escalated");
  });
}

export async function addNoteAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const body = str(fd, "body");
    if (!body) return invalid(locale, { body: getT(locale)("concierge.errMessage") });
    const api = await userApi();
    await unwrap(api.concierge.POST("/concierge/cases/{id}/notes", { params: { path: { id: str(fd, "case_id") } }, body: { body: body.slice(0, 4000) } }));
    refresh();
    return getT(locale)("concierge.noteAdded");
  });
}

export async function proposeOptionAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const providerId = str(fd, "provider_id");
    if (!/^[A-Za-z0-9-]{10,36}$/.test(providerId)) return invalid(locale, { provider_id: getT(locale)("fp.errProviderId") });
    const api = await userApi();
    await unwrap(
      api.concierge.POST("/concierge/cases/{id}/options", {
        params: { path: { id: str(fd, "case_id") } },
        body: {
          provider_id: providerId,
          facility_id: optStr(fd, "facility_id") ?? null,
          branch_id: optStr(fd, "branch_id") ?? null,
          service_id: optStr(fd, "service_id") ?? null,
          label: optStr(fd, "label")?.slice(0, 200) ?? null,
        },
      }),
    );
    refresh();
    return getT(locale)("concierge.optionProposed");
  });
}
