import { describe, expect, it, vi } from "vitest";

import {
  LOCALE_INFO,
  createTranslator,
  currencyExponent,
  dirOf,
  formatDate,
  formatMoney,
  formatWallTime,
  getTranslator,
  negotiateLocale,
  placeholdersOf,
  timeZoneLabel,
  weekdayName,
} from "../src/index";

describe("locales", () => {
  it("ar and fa are RTL, others LTR", () => {
    expect(dirOf("ar")).toBe("rtl");
    expect(dirOf("fa")).toBe("rtl");
    expect(dirOf("en")).toBe("ltr");
    expect(LOCALE_INFO.fr.dir).toBe("ltr");
  });

  it("negotiates Accept-Language with q-values against launch locales", () => {
    expect(negotiateLocale("fa-IR,fa;q=0.9,en;q=0.8")).toBe("fa");
    expect(negotiateLocale("de-DE,de;q=0.9,ar;q=0.5")).toBe("ar");
    expect(negotiateLocale("ru")).toBe("en");
    expect(negotiateLocale("en;q=0.1, ar;q=0.9")).toBe("ar");
    expect(negotiateLocale(null)).toBe("en");
  });
});

describe("money", () => {
  it("formats AED minor units", () => {
    expect(currencyExponent("AED")).toBe(2);
    expect(formatMoney(125050, "AED", "en")).toMatch(/AED\s?1,250\.50/);
    expect(formatMoney(50000, "AED", "en", { trimWholeUnits: true })).toMatch(/AED\s?500$/);
  });

  it("uses locale digits/separators for ar and fa", () => {
    const ar = formatMoney(125050, "AED", "ar");
    const fa = formatMoney(125050, "AED", "fa");
    expect(ar).toContain("AED");
    expect(fa).toContain("AED");
    expect(fa).not.toContain("1,250"); // Persian digits
  });

  it("rejects fractional minor units", () => {
    expect(() => formatMoney(10.5, "AED", "en")).toThrow(TypeError);
  });
});

describe("dates and times", () => {
  it("keeps calendar dates on the same day regardless of host time zone", () => {
    expect(formatDate("2027-01-31", "en", { year: "numeric", month: "long", day: "numeric" })).toBe("31 January 2027");
  });

  it("formats branch wall-clock times and ISO weekdays (0 = Monday)", () => {
    expect(formatWallTime("09:00", "en")).toMatch(/^9:00\s?(am|AM)$/);
    expect(formatWallTime("24:00", "en")).toMatch(/^12:00\s?(am|AM)$/);
    expect(weekdayName(0, "en")).toBe("Monday");
    expect(weekdayName(6, "en")).toBe("Sunday");
    expect(weekdayName(4, "ar")).toBe("الجمعة");
  });

  it("labels IANA zones", () => {
    expect(timeZoneLabel("Asia/Dubai", "en", new Date("2026-01-01T00:00:00Z"))).toBe("GMT+4");
  });
});

describe("translator", () => {
  it("formats ICU plurals per locale", () => {
    const t = getTranslator("en");
    expect(t("common.results", { count: 0 })).toBe("No results");
    expect(t("common.results", { count: 1 })).toBe("1 result");
    expect(t("common.results", { count: 12 })).toBe("12 results");
    expect(getTranslator("ar")("common.results", { count: 2 })).toBe("نتيجتان");
  });

  it("falls back to English for scaffold locales, then to the key", () => {
    const onMissing = vi.fn();
    const t = getTranslator("fr", { onMissing });
    expect(t("common.save")).toBe("Enregistrer");
    expect(t("errors.not_found")).toBe("We couldn’t find what you were looking for.");
    expect(t("does.not.exist")).toBe("does.not.exist");
    expect(onMissing).toHaveBeenCalledWith("does.not.exist", "fr");
  });

  it("treats markup as text (no HTML injection through messages)", () => {
    const t = createTranslator("en", { en: { x: "Hello <b>{name}</b>" } });
    expect(t("x", { name: "<img>" })).toBe("Hello <b><img></b>");
  });

  it("extracts placeholders from nested ICU", () => {
    expect(placeholdersOf("{type, select, doctor {Dr. {name}} other {{name}}} has {count, plural, one {# slot} other {# slots}}")).toEqual([
      "count",
      "name",
      "type",
    ]);
  });
});
