import "server-only";

import type { Translator } from "@healuxa/i18n";

import { EXPIRY_CHOICES, PURPOSES, RECORD_TYPES } from "@/lib/records";

import type { ShareLabels } from "./ShareDialog";

export function shareLabels(t: Translator, trigger?: string): ShareLabels {
  return {
    trigger: trigger ?? t("records.share"),
    title: t("records.shareTitle"),
    records: t("records.shareRecordsLabel"),
    shareWith: t("records.shareWith"),
    careTeam: t("records.careTeam"),
    search: t("records.searchLabel"),
    searchPlaceholder: t("records.searchPlaceholder"),
    searching: t("records.searching"),
    noMatches: t("records.noMatches"),
    noCareTeam: t("records.noCareTeam"),
    kindProvider: t("records.kindProvider"),
    kindFacility: t("records.kindFacility"),
    expiry: t("records.expiry"),
    purpose: t("records.purpose"),
    submit: t("records.shareSubmit"),
    sharing: t("records.sharing"),
    cancel: t("common.cancel"),
    close: t("common.close"),
    detail: t("errors.detailLabel"),
    reference: t("errors.referenceLabel"),
  };
}

export const expiryOptions = (t: Translator) => EXPIRY_CHOICES.map((d) => ({ value: String(d), label: t("records.expiryDays", { days: d }) }));
export const purposeOptions = (t: Translator) => PURPOSES.map((p) => ({ value: p, label: t(`records.purposes.${p}`) }));
export const typeOptions = (t: Translator) => RECORD_TYPES.map((v) => ({ value: v, label: t(`records.types.${v}`) }));
