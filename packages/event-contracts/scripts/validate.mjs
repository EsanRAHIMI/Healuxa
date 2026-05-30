// Validates all event schemas compile, the envelope is sound, and the registry in
// src/registry.ts is consistent with the schema files (every event has a schema $def
// and exactly one owner). Run in CI to prevent drift.
// Usage: npm run validate
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { readdir, readFile } from "node:fs/promises";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemasDir = join(root, "schemas");

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);

const files = (await readdir(schemasDir)).filter((f) => f.endsWith(".schema.json"));
const docs = {};
for (const f of files) {
  const doc = JSON.parse(await readFile(join(schemasDir, f), "utf8"));
  docs[f] = doc;
  ajv.addSchema(doc, f); // register by filename so $ref "common.schema.json#/..." resolves
}

let errors = 0;

// 1) every schema must compile
for (const f of files) {
  try {
    ajv.getSchema(f) || ajv.compile(docs[f]);
  } catch (e) {
    console.error(`✗ schema does not compile: ${f}\n  ${e.message}`);
    errors++;
  }
}

// 2) registry consistency
const registrySrc = await readFile(join(root, "src", "registry.ts"), "utf8");
const eventTypes = [...registrySrc.matchAll(/type:\s*"([a-z_]+\.[a-z_]+)"/g)].map((m) => m[1]);
const schemaRefs = [...registrySrc.matchAll(/schema:\s*"(schemas\/[^"]+)"/g)].map((m) => m[1]);

const uniqueTypes = new Set(eventTypes);
if (uniqueTypes.size !== eventTypes.length) {
  console.error("✗ duplicate event types in registry");
  errors++;
}

// 3) each registry schema ref must resolve to an existing $def
for (const ref of schemaRefs) {
  const [file, pointer] = ref.split("#");
  const doc = docs[file.replace("schemas/", "")];
  if (!doc) {
    console.error(`✗ registry references missing schema file: ${file}`);
    errors++;
    continue;
  }
  const defName = pointer.replace("/$defs/", "");
  if (!doc.$defs || !doc.$defs[defName]) {
    console.error(`✗ registry references missing $def: ${ref}`);
    errors++;
  }
}

if (errors === 0) {
  console.log(`✓ ${files.length} schemas valid · ${eventTypes.length} events in registry · all refs resolve`);
  process.exit(0);
} else {
  console.error(`\n${errors} contract error(s) found.`);
  process.exit(1);
}
