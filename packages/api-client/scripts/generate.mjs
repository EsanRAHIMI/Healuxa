// Generates typed path/schema definitions from packages/api-contracts/openapi/*.openapi.yaml.
//   npm run generate          -> (re)write src/generated/<service>.ts
//   npm run check:generated   -> fail if the committed files are stale (used in CI)
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const contracts = resolve(here, "../../api-contracts/openapi");
const outDir = resolve(here, "../src/generated");
const check = process.argv.includes("--check");

// Services the platform clients talk to.
const SERVICES = ["identity", "provider", "profile", "assessment", "appointment", "concierge", "notification", "payment", "subscription"];

const header = (name) =>
  `/**\n * GENERATED from packages/api-contracts/openapi/${name}.openapi.yaml by openapi-typescript.\n * Do not edit by hand: run \`npm run generate -w @healuxa/api-client\`.\n */\n\n`;

await mkdir(outDir, { recursive: true });
let stale = 0;
for (const name of SERVICES) {
  const spec = pathToFileURL(join(contracts, `${name}.openapi.yaml`));
  const ast = await openapiTS(spec, { alphabetize: false, exportType: false });
  const contents = header(name) + astToString(ast);
  const target = join(outDir, `${name}.ts`);
  if (check) {
    const current = await readFile(target, "utf8").catch(() => "");
    if (current !== contents) {
      console.error(`stale: src/generated/${name}.ts (run npm run generate -w @healuxa/api-client)`);
      stale++;
    }
  } else {
    await writeFile(target, contents);
    console.log(`generated src/generated/${name}.ts`);
  }
}
process.exit(stale === 0 ? 0 : 1);
