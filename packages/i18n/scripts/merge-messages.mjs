// Deep-merges messages/_add_<locale>*.json into messages/<locale>.json and deletes the add files.
// Authoring helper for large catalog additions:  node scripts/merge-messages.mjs en ar fa
import { readFileSync, readdirSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "messages");

function merge(target, source, path = "") {
  for (const [k, v] of Object.entries(source)) {
    const p = path ? `${path}.${k}` : k;
    if (typeof v === "object" && v !== null) {
      if (typeof target[k] === "string") throw new Error(`conflict at ${p}`);
      target[k] = merge(target[k] ?? {}, v, p);
    } else {
      if (typeof target[k] === "object") throw new Error(`conflict at ${p}`);
      target[k] = v;
    }
  }
  return target;
}

for (const locale of process.argv.slice(2)) {
  const file = join(dir, `${locale}.json`);
  const base = JSON.parse(readFileSync(file, "utf8"));
  const adds = readdirSync(dir).filter((f) => f.startsWith(`_add_${locale}`) && f.endsWith(".json")).sort();
  for (const add of adds) {
    merge(base, JSON.parse(readFileSync(join(dir, add), "utf8")));
    unlinkSync(join(dir, add));
  }
  writeFileSync(file, `${JSON.stringify(base, null, 2)}\n`);
  console.log(`${locale}: merged ${adds.length} file(s)`);
}
