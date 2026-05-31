import assert from "node:assert/strict";
import test from "node:test";
import { buildErrorBody, parseHealuxaHeaders, requirePermission } from "../dist/index.js";

test("buildErrorBody matches shared error schema", () => {
  const body = buildErrorBody({
    status: 401,
    code: "unauthorized",
    title: "Unauthorized",
    traceId: "trace-1",
  });
  assert.equal(body.code, "unauthorized");
  assert.equal(body.trace_id, "trace-1");
});

test("parseHealuxaHeaders reads edge-injected headers", () => {
  const headers = new Headers({
    "x-healuxa-user": "user-1",
    "x-healuxa-tenant": "healuxa-dubai",
    "x-healuxa-perms": "iam:read,iam:write",
  });
  const parsed = parseHealuxaHeaders(headers);
  assert.equal(parsed.user, "user-1");
  assert.deepEqual(parsed.permissions, ["iam:read", "iam:write"]);
});

test("requirePermission enforces RBAC", () => {
  assert.throws(() => requirePermission({}, "iam:read"));
});
