// Generates TypeScript types for each spec using openapi-typescript.
// Usage: npm run generate:ts
import { readdir, mkdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const openapiDir = join(root, "openapi");
const outDir = join(root, "generated");

await mkdir(outDir, { recursive: true });
const files = (await readdir(openapiDir)).filter((f) => f.endsWith(".openapi.yaml"));

let failed = 0;
for (const f of files) {
  const name = f.replace(".openapi.yaml", "");
  const out = join(outDir, `${name}.d.ts`);
  const r = spawnSync("npx", ["openapi-typescript", join(openapiDir, f), "-o", out], {
    stdio: "inherit",
  });
  if (r.status !== 0) failed++;
}
console.log(failed === 0 ? "✓ generated TS types" : `✗ ${failed} spec(s) failed`);
process.exit(failed === 0 ? 0 : 1);
