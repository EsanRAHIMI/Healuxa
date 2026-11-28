import { getTranslator } from "@healuxa/i18n";
import { describe, expect, it } from "vitest";

import { GOAL_CODES, INTAKE_QUESTIONS, ULID, isGoalCode, phaseLabel, stepLabel } from "../journey";

const t = getTranslator("en");

describe("journey vocabulary", () => {
  it("has a label and description for every goal in every launch locale", () => {
    for (const locale of ["en", "ar", "fa"] as const) {
      const tr = getTranslator(locale, { onMissing: (key) => { throw new Error(`missing ${locale}:${key}`); } });
      for (const goal of GOAL_CODES) {
        expect(tr(`journey.goal.${goal}`)).not.toBe("");
        expect(tr(`journey.goalBody.${goal}`)).not.toBe("");
      }
      for (const q of INTAKE_QUESTIONS) {
        expect(tr(`journey.intake.${q.code}`)).not.toBe("");
        if (q.code !== "language") for (const o of q.options) expect(tr(`journey.intake.${q.code}_${o}`)).not.toBe("");
      }
    }
  });

  it("only accepts contract goal codes", () => {
    expect(isGoalCode("skin_health")).toBe(true);
    expect(isGoalCode("cure_everything")).toBe(false);
  });

  it("labels steps from code and goal, falling back to the API title for unknown codes", () => {
    expect(stepLabel(t, { code: "consultation", goal: "dental_smile", title: "x" })).toBe("Consultation — Dental and smile");
    expect(stepLabel(t, { code: "intake_assessment", goal: null, title: "x" })).toBe("Tell us your preferences");
    expect(stepLabel(t, { code: "something_new", goal: null, title: "Server title" })).toBe("Server title");
    expect(phaseLabel(t, { code: "consult", name: "x" })).toBe("Consult a verified practitioner");
    expect(phaseLabel(t, { code: null, name: "Legacy phase" })).toBe("Legacy phase");
  });

  it("matches ULIDs only", () => {
    expect(ULID.test("01M7DEADC0ST0RFVJ9W7BT87QP")).toBe(true);
    expect(ULID.test("01M7DEADC0ST0RFVJ9W7BT87Q")).toBe(false);
    expect(ULID.test("../../etc/passwd-0000000000")).toBe(false);
  });
});
