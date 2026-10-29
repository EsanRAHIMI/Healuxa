// Regenerates manifest.json `needs_professional_review.keys` from the English catalog.
//   npm run manifest -w @healuxa/i18n           -> rewrite
//   npm run manifest -w @healuxa/i18n -- --check -> fail if stale (CI / tests)
// Policy fields (namespaces, extra_keys, locale status, ui_chrome_allowlist) are edited by hand.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = join(root, "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const en = JSON.parse(readFileSync(join(root, "messages", "en.json"), "utf8"));

const flat = {};
(function walk(tree, prefix) {
  for (const [k, v] of Object.entries(tree)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") flat[key] = v;
    else walk(v, key);
  }
})(en, "");

const review = manifest.needs_professional_review;
const keys = Object.keys(flat)
  .filter((k) => review.namespaces.some((ns) => k === ns || k.startsWith(`${ns}.`)) || review.extra_keys.includes(k))
  .sort();

if (process.argv.includes("--check")) {
  if (JSON.stringify(keys) !== JSON.stringify(review.keys)) {
    console.error("manifest.json needs_professional_review.keys is stale: run npm run manifest -w @healuxa/i18n");
    process.exit(1);
  }
} else {
  review.keys = keys;
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`flagged ${keys.length} keys for professional review`);
}
