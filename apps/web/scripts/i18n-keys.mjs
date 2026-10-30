// Lists translation keys used in apps/web/src that are missing from the English catalog.
//   node scripts/i18n-keys.mjs           -> print missing keys (exit 1 if any)
// Literal t("a.b") keys are checked exactly; template keys t(`enums.x.${v}`) are checked by prefix.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const en = JSON.parse(readFileSync(join(root, "../../packages/i18n/messages/en.json"), "utf8"));
const flat = new Set();
(function walk(tree, prefix) {
  for (const [k, v] of Object.entries(tree)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") flat.add(key);
    else walk(v, key);
  }
})(en, "");

function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|mjs)$/.test(f) ? [p] : [];
  });
}

const missing = new Set();
const prefixes = new Set();
for (const file of files(join(root, "src"))) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/\bt\(\s*"([a-zA-Z0-9_.]+)"/g)) if (!flat.has(m[1])) missing.add(m[1]);
  for (const m of src.matchAll(/\bt\(\s*`([a-zA-Z0-9_.]+)\$\{/g)) prefixes.add(m[1]);
}
const missingPrefixes = [...prefixes].filter((p) => ![...flat].some((k) => k.startsWith(p)));
for (const k of [...missing].sort()) console.log(k);
for (const p of missingPrefixes.sort()) console.log(`${p}*`);
process.exit(missing.size || missingPrefixes.length ? 1 : 0);
