// Writes css/tokens.css and css/theme.css from src/. `--check` fails if the committed files are stale.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { buildTailwindThemeCss, buildTokensCss } from "../src/css.ts";

const outDir = join(dirname(fileURLToPath(import.meta.url)), "..", "css");
const outputs: Record<string, string> = { "tokens.css": buildTokensCss(), "theme.css": buildTailwindThemeCss() };
const check = process.argv.includes("--check");

await mkdir(outDir, { recursive: true });
let stale = 0;
for (const [name, contents] of Object.entries(outputs)) {
  const target = join(outDir, name);
  if (check) {
    const current = await readFile(target, "utf8").catch(() => "");
    if (current !== contents) {
      console.error(`stale: css/${name} (run npm run build -w @healuxa/design-tokens)`);
      stale++;
    }
  } else {
    await writeFile(target, contents);
    console.log(`wrote css/${name}`);
  }
}
process.exit(stale ? 1 : 0);
