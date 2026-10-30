"use server";

/** notification-service: inbox read state and per-category channel preferences. */
import { unwrap, type NotificationPreferencesUpdate } from "@healuxa/api-client";
import { refresh } from "next/cache";

import { act, actionSession, invalid } from "@/lib/actions";
import { userApi } from "@/lib/api";
import { str, type FormState } from "@/lib/forms";
import { getT } from "@/lib/i18n";
import { NOTIFICATION_CATEGORIES, NOTIFICATION_CHANNELS } from "@/lib/notify";
import { isValidTimeZone } from "@/lib/time";

export async function markReadAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    await actionSession();
    const api = await userApi();
    const id = str(fd, "notification_id");
    if (id) await unwrap(api.notification.POST("/notifications/{id}/read", { params: { path: { id } } }));
    else await unwrap(api.notification.POST("/notifications/read-all"));
    refresh();
    return { ok: true, at: Date.now() };
  });
}

export async function savePreferencesAction(_prev: FormState, fd: FormData): Promise<FormState> {
  return act(fd, async (locale) => {
    const session = await actionSession();
    const t = getT(locale);
    const timezone = str(fd, "timezone");
    if (!isValidTimeZone(timezone)) return invalid(locale, { timezone: t("pp.errTimezone") });
    const qs = str(fd, "quiet_start");
    const qe = str(fd, "quiet_end");
    const prefLocale = str(fd, "pref_locale");
    const channels: NonNullable<NotificationPreferencesUpdate["channels"]> = {};
    for (const cat of NOTIFICATION_CATEGORIES) {
      channels[cat] = Object.fromEntries(NOTIFICATION_CHANNELS.map((ch) => [ch, fd.get(`${cat}.${ch}`) === "on"]));
    }
    const body: NotificationPreferencesUpdate = {
      timezone,
      marketing_opt_in: fd.get("marketing_opt_in") === "on",
      quiet_hours: qs && qe ? { start: qs, end: qe } : null,
      channels,
      ...(prefLocale === "en" || prefLocale === "ar" || prefLocale === "fa" ? { locale: prefLocale } : {}),
    };
    const api = await userApi();
    await unwrap(api.notification.PUT("/notifications/preferences/{userId}", { params: { path: { userId: session.userId } }, body }));
    refresh();
    return t("notifications.saved");
  });
}
