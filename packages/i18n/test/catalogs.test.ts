import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { LAUNCH_LOCALES, LOCALES, SCAFFOLD_LOCALES, catalogs, flatten, placeholdersOf } from "../src/index";

const root = join(import.meta.dirname, "..");
const manifest = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8")) as {
  locales: Record<string, { status: string }>;
  needs_professional_review: { namespaces: string[]; extra_keys: string[]; keys: string[] };
  ui_chrome_allowlist: string[];
};
const en = flatten(catalogs.en);

describe("launch-locale completeness", () => {
  it.each(LAUNCH_LOCALES.filter((l) => l !== "en"))("%s has every English key and no extras", (locale) => {
    const flat = flatten(catalogs[locale]);
    const missing = Object.keys(en).filter((k) => !(k in flat));
    const extra = Object.keys(flat).filter((k) => !(k in en));
    expect(missing, `${locale} is missing keys`).toEqual([]);
    expect(extra, `${locale} has keys that English does not`).toEqual([]);
  });

  it.each(LAUNCH_LOCALES.filter((l) => l !== "en"))("%s keeps the same ICU placeholders and non-empty strings", (locale) => {
    const flat = flatten(catalogs[locale]);
    for (const [key, source] of Object.entries(en)) {
      const translated = flat[key]!;
      expect(translated.trim(), `${locale}:${key} is empty`).not.toBe("");
      expect(placeholdersOf(translated), `${locale}:${key} placeholders`).toEqual(placeholdersOf(source));
    }
  });

  it("every English message is valid ICU", () => {
    for (const [key, message] of Object.entries(en)) expect(() => placeholdersOf(message), key).not.toThrow();
  });
});

describe("scaffold locales", () => {
  it.each(SCAFFOLD_LOCALES)("%s only contains keys that exist in English", (locale) => {
    const flat = flatten(catalogs[locale]);
    expect(Object.keys(flat).filter((k) => !(k in en))).toEqual([]);
  });

  it("manifest declares a status for every locale", () => {
    expect(Object.keys(manifest.locales).sort()).toEqual([...LOCALES].sort());
    for (const l of LAUNCH_LOCALES) if (l !== "en") expect(manifest.locales[l]!.status).toBe("machine_draft");
  });
});

describe("professional review manifest", () => {
  it("flags every legal/consent/clinical/payment key (manifest is up to date)", () => {
    expect(() => execFileSync(process.execPath, [join(root, "scripts/manifest.mjs"), "--check"], { stdio: "pipe" })).not.toThrow();
    const flagged = new Set(manifest.needs_professional_review.keys);
    for (const key of Object.keys(en)) {
      if (manifest.needs_professional_review.namespaces.some((ns) => key.startsWith(`${ns}.`))) expect(flagged.has(key), key).toBe(true);
    }
  });

  it("every flagged key exists", () => {
    for (const key of manifest.needs_professional_review.keys) expect(en[key], key).toBeDefined();
  });

  // Guard against sensitive copy slipping into UI-chrome namespaces unflagged.
  const SENSITIVE =
    /\b(consent|privacy notice|terms of use|refund|payment|pay |invoice|diagnos\w*|treatment plan|prescri\w*|medical advice|guarantee\w*|cure\w*|liabilit\w*|insurance cover\w*)\b/i;
  it("sensitive wording outside flagged namespaces is flagged or explicitly allow-listed as UI chrome", () => {
    const flagged = new Set([...manifest.needs_professional_review.keys, ...manifest.ui_chrome_allowlist]);
    const offenders = Object.entries(en)
      .filter(([key, text]) => SENSITIVE.test(text) && !flagged.has(key))
      .map(([key]) => key);
    expect(offenders).toEqual([]);
  });
});
