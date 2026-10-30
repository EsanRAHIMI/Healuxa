"use server";

import { idempotencyHeader, unwrap, type FacilityType, type StaffRole, type TimeWindow } from "@healuxa/api-client";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { optNumber, optStr, str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";
import { FACILITY_TYPES } from "@/lib/query";
import { forgetFacility, rememberFacility } from "@/lib/remembered";
import { hhmmToMinutes, isValidTimeZone } from "@/lib/time";

const ID = /^[A-Za-z0-9-]{10,36}$/;

function descriptionFrom(fd: FormData): Record<string, string> {
  const out: Record<string, string> = {};
  for (const l of ["en", "ar", "fa"]) {
    const v = str(fd, `description_${l}`);
    if (v) out[l] = v.slice(0, 4000);
  }
  return out;
}

export async function registerFacilityAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const errors: Record<string, string> = {};
    const type = str(fd, "type");
    if (!FACILITY_TYPES.includes(type as FacilityType)) errors.type = t("fp.errType");
    if (str(fd, "name").length < 2) errors.name = t("fp.errName");
    if (str(fd, "license_authority").length < 2) errors.license_authority = t("pp.errAuthority");
    if (str(fd, "license_number").length < 2) errors.license_number = t("pp.errNumber");
    const website = optStr(fd, "website");
    if (website && !/^https:\/\/[^\s]+\.[^\s]+$/.test(website)) errors.website = t("fp.errWebsite");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    const facility = await unwrap(
      api.provider.POST("/facilities", {
        params: { header: idempotencyHeader(str(fd, "idempotency_key") || undefined) },
        body: {
          type: type as FacilityType,
          name: str(fd, "name"),
          license_authority: str(fd, "license_authority"),
          license_number: str(fd, "license_number"),
          description: descriptionFrom(fd),
          ...(website ? { website } : {}),
          ...(optStr(fd, "phone") ? { phone: str(fd, "phone") } : {}),
        },
      }),
    );
    await rememberFacility(facility.id);
    target = `/${locale}/facility/${facility.id}?registered=1`;
  }, (locale) => ({ conflict: getT(locale)("fp.licenceTaken") }));
  if (state.ok && target) redirect(target);
  return state;
}

export async function openFacilityAction(_prev: FormState, fd: FormData): Promise<FormState> {
  let target = "";
  const state = await act(fd, async (locale) => {
    await actionSession();
    const id = str(fd, "facility_id");
    if (!ID.test(id)) return invalid(locale, { facility_id: getT(locale)("fp.errFacilityId") });
    const api = await userApi();
    // Staff-only list: succeeds only for this facility's staff (or platform staff).
    await unwrap(api.provider.GET("/facilities/{facility_id}/staff", { params: { path: { facility_id: id } } }));
    await rememberFacility(id);
    target = `/${locale}/facility/${id}`;
  }, (locale) => ({ forbidden: getT(locale)("fp.notStaff"), not_found: getT(locale)("fp.notStaff") }));
  if (state.ok && target) redirect(target);
  return state;
}

export async function forgetFacilityAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async () => {
    await forgetFacility(str(fd, "facility_id"));
    refresh();
  });
}

export async function updateFacilityAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    if (str(fd, "name").length < 2) return invalid(locale, { name: t("fp.errName") });
    const website = str(fd, "website");
    if (website && !/^https:\/\/[^\s]+\.[^\s]+$/.test(website)) return invalid(locale, { website: t("fp.errWebsite") });
    const api = await userApi();
    await unwrap(
      api.provider.PATCH("/facilities/{facility_id}", {
        params: { path: { facility_id: str(fd, "facility_id") } },
        body: { name: str(fd, "name"), description: descriptionFrom(fd), website, phone: str(fd, "phone") },
      }),
    );
    refresh();
    return t("fp.saved");
  });
}

export async function createBranchAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const errors: Record<string, string> = {};
    for (const f of ["name", "address_line", "city"]) if (str(fd, f).length < 2) errors[f] = t("fp.errRequired");
    const country = str(fd, "country").toUpperCase();
    if (!/^[A-Z]{2}$/.test(country)) errors.country = t("fp.errCountry");
    const timezone = str(fd, "timezone");
    if (!isValidTimeZone(timezone)) errors.timezone = t("pp.errTimezone");
    const lat = optNumber(fd, "latitude");
    const lng = optNumber(fd, "longitude");
    if (lat !== undefined && (Number.isNaN(lat) || lat < -90 || lat > 90)) errors.latitude = t("fp.errLatitude");
    if (lng !== undefined && (Number.isNaN(lng) || lng < -180 || lng > 180)) errors.longitude = t("fp.errLongitude");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(
      api.provider.POST("/facilities/{facility_id}/branches", {
        params: { path: { facility_id: str(fd, "facility_id") } },
        body: {
          name: str(fd, "name"),
          address_line: str(fd, "address_line"),
          city: str(fd, "city"),
          country,
          timezone,
          ...(optStr(fd, "emirate") ? { emirate: str(fd, "emirate") } : {}),
          ...(optStr(fd, "phone") ? { phone: str(fd, "phone") } : {}),
          ...(lat !== undefined ? { latitude: lat } : {}),
          ...(lng !== undefined ? { longitude: lng } : {}),
        },
      }),
    );
    refresh();
    return t("fp.branchCreated");
  });
}

/** Weekly hours editor: fields open_<d>, start_<d>, end_<d> and optional second window start2_<d>/end2_<d>. */
export async function replaceHoursAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const windows: TimeWindow[] = [];
    const errors: Record<string, string> = {};
    for (let d = 0; d < 7; d++) {
      if (fd.get(`open_${d}`) !== "on") continue;
      for (const suffix of ["", "2"]) {
        const start = str(fd, `start${suffix}_${d}`);
        const end = str(fd, `end${suffix}_${d}`);
        if (suffix === "2" && !start && !end) continue;
        const s = hhmmToMinutes(start);
        const e = hhmmToMinutes(end === "00:00" ? "24:00" : end, true);
        if (Number.isNaN(s) || Number.isNaN(e) || e <= s) {
          errors[`end${suffix}_${d}`] = t("pp.errTimeOrder");
          continue;
        }
        windows.push({ weekday: d, start, end: end === "00:00" ? "24:00" : end });
      }
    }
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(api.provider.PUT("/branches/{branch_id}/operating-hours", { params: { path: { branch_id: str(fd, "branch_id") } }, body: { windows } }));
    refresh();
    return t("fp.hoursSaved");
  }, (locale) => ({ unprocessable: getT(locale)("fp.hoursInvalid") }));
}

export async function addStaffAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const userId = str(fd, "user_id");
    const role = str(fd, "role") as StaffRole;
    const errors: Record<string, string> = {};
    if (!ID.test(userId)) errors.user_id = t("fp.errUserId");
    if (!["facility_admin", "scheduler", "billing"].includes(role)) errors.role = t("fp.errRole");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(api.provider.POST("/facilities/{facility_id}/staff", { params: { path: { facility_id: str(fd, "facility_id") } }, body: { user_id: userId, role } }));
    refresh();
    return t("fp.staffAdded");
  }, (locale) => ({ conflict: getT(locale)("fp.staffExists") }));
}

export async function removeStaffAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    await unwrap(
      api.provider.DELETE("/facilities/{facility_id}/staff/{user_id}", { params: { path: { facility_id: str(fd, "facility_id"), user_id: str(fd, "user_id") } } }),
    );
    refresh();
    return getT(locale)("fp.staffRemoved");
  }, (locale) => ({ conflict: getT(locale)("fp.lastAdmin") }));
}

export async function inviteProviderAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const t = getT(locale);
    const providerId = str(fd, "provider_id");
    const branchId = str(fd, "branch_id");
    const errors: Record<string, string> = {};
    if (!ID.test(providerId)) errors.provider_id = t("fp.errProviderId");
    if (!branchId) errors.branch_id = t("pp.errBranch");
    if (Object.keys(errors).length) return invalid(locale, errors);
    const api = await userApi();
    await unwrap(api.provider.POST("/affiliations", { body: { provider_id: providerId, branch_id: branchId } }));
    refresh();
    return t("fp.invited");
  }, (locale) => ({ conflict: getT(locale)("pp.affiliationExists"), not_found: getT(locale)("fp.providerNotFound") }));
}
