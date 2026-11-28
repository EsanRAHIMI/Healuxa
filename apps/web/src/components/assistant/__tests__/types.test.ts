import { describe, expect, it } from "vitest";

import { cardHref, fill, formatCardMoney, parseSseChunk } from "../types";

describe("parseSseChunk", () => {
  it("parses complete events and keeps the partial remainder", () => {
    const buffer = 'event: session\ndata: {"session_id":"01ABC"}\n\nevent: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"te';
    const { events, rest } = parseSseChunk(buffer);
    expect(events).toEqual([
      { event: "session", data: { session_id: "01ABC" } },
      { event: "delta", data: { text: "Hel" } },
    ]);
    expect(rest).toBe('event: delta\ndata: {"te');
  });

  it("skips malformed events", () => {
    expect(parseSseChunk("event: delta\ndata: {nope\n\n").events).toEqual([]);
  });
});

describe("cardHref", () => {
  it("prefixes server-built relative paths with the locale", () => {
    expect(cardHref("ar", "/book/01SERVICE?milestone=01STEP")).toBe("/ar/book/01SERVICE?milestone=01STEP");
  });
  it.each(["https://evil.example/x", "//evil.example/x", "/\\evil", "", null, undefined, "javascript:alert(1)"])("rejects %s", (href) => {
    expect(cardHref("en", href as string | null | undefined)).toBeNull();
  });
});

describe("formatting", () => {
  it("fills placeholders and leaves unknown ones", () => {
    expect(fill("From {price} {x}", { price: "AED 450.00" })).toBe("From AED 450.00 {x}");
  });
  it("formats minor units as currency", () => {
    expect(formatCardMoney({ amount_minor: 45000, currency: "AED" }, "en-AE")).toMatch(/AED\s?450\.00/);
  });
});
