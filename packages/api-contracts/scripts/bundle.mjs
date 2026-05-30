// Bundles (dereferences) each *.openapi.yaml into dist/<name>.bundled.yaml using @redocly/cli.
// Usage: npm run bundle
import { readdir, mkdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const openapiDir = join(root, "openapi");
const distDir = join(root, "dist");

await mkdir(distDir, { recursive: true });
const files = (await readdir(openapiDir)).filter((f) => f.endsWith(".openapi.yaml"));

let failed = 0;
for (const f of files) {
  const name = f.replace(".openapi.yaml", "");
  const out = join(distDir, `${name}.bundled.yaml`);
  const r = spawnSync("npx", ["redocly", "bundle", join(openapiDir, f), "-o", out], {
    stdio: "inherit",
  });
  if (r.status !== 0) failed++;
}
process.exit(failed === 0 ? 0 : 1);
