import { test } from "node:test";
import assert from "node:assert/strict";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { readFile } from "node:fs/promises";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemasDir = join(root, "schemas");

async function loadAjv() {
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  for (const f of ["common.schema.json", "envelope.schema.json", "journey.schema.json", "appointment.schema.json"]) {
    ajv.addSchema(JSON.parse(await readFile(join(schemasDir, f), "utf8")), f);
  }
  return ajv;
}

test("a well-formed envelope validates", async () => {
  const ajv = await loadAjv();
  const validate = ajv.getSchema("envelope.schema.json");
  const ok = validate({
    event_id: "01J9ZABCDEFGH012345678",
    type: "journey.milestone_completed",
    version: 1,
    schema_ref: "https://contracts.healuxa.com/events/journey/milestone_completed/v1",
    occurred_at: "2026-05-30T16:00:00Z",
    tenant_id: "healuxa-dubai",
    producer: "transformation-engine",
    payload: { journey_id: "01J9ZJOURNEY00000000001", user_id: "01J9ZUSER00000000000001", milestone_id: "01J9ZMILE00000000000001", completed_at: "2026-05-30T16:00:00Z" },
  });
  assert.equal(ok, true, JSON.stringify(validate.errors));
});

test("an envelope with a bad type pattern fails", async () => {
  const ajv = await loadAjv();
  const validate = ajv.getSchema("envelope.schema.json");
  const ok = validate({
    event_id: "01J9ZABCDEFGH012345678",
    type: "JourneyMilestoneCompleted",
    version: 1,
    schema_ref: "https://x/y",
    occurred_at: "2026-05-30T16:00:00Z",
    tenant_id: "healuxa-dubai",
    producer: "transformation-engine",
    payload: {},
  });
  assert.equal(ok, false);
});

test("milestone payload rejects unknown fields (additionalProperties: false)", async () => {
  const ajv = await loadAjv();
  const validate = ajv.getSchema("journey.schema.json#/$defs/JourneyMilestoneCompleted");
  const ok = validate({
    journey_id: "01J9ZJOURNEY00000000001",
    user_id: "01J9ZUSER00000000000001",
    milestone_id: "01J9ZMILE00000000000001",
    completed_at: "2026-05-30T16:00:00Z",
    surprise_field: "drift!",
  });
  assert.equal(ok, false);
});
