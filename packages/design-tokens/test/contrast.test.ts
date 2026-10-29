import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  buildTailwindThemeCss,
  buildTokensCss,
  colorVariableNames,
  colors,
  contrastPairs,
  contrastRatio,
  tailwindPreset,
} from "../src/index.ts";

describe("contrastRatio", () => {
  it("matches WCAG reference values", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2);
    expect(contrastRatio("#FFFFFF", "#FFFFFF")).toBe(1);
  });
});

describe.each(["light", "dark"] as const)("%s scheme meets WCAG 2.2 AA", (scheme) => {
  const palette = colors[scheme];
  it.each(contrastPairs.map((p) => [`${p.fg} on ${p.bg} (${p.usage})`, p] as const))("%s", (_label, pair) => {
    const ratio = contrastRatio(palette[pair.fg], palette[pair.bg]);
    expect(ratio, `${scheme}: ${pair.fg} ${palette[pair.fg]} on ${pair.bg} ${palette[pair.bg]} = ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(pair.min);
  });
});

describe("generated CSS", () => {
  it("defines every colour for both schemes", () => {
    const css = buildTokensCss();
    for (const name of colorVariableNames) {
      expect(css.split(`${name}:`).length - 1, name).toBe(3); // light, [data-theme=dark], prefers-color-scheme
    }
    expect(css).toContain("prefers-reduced-motion");
  });

  it("is committed and up to date", () => {
    const dir = join(import.meta.dirname, "..", "css");
    expect(readFileSync(join(dir, "tokens.css"), "utf8")).toBe(buildTokensCss());
    expect(readFileSync(join(dir, "theme.css"), "utf8")).toBe(buildTailwindThemeCss());
  });

  it("restricts the Tailwind palette to semantic tokens", () => {
    const theme = buildTailwindThemeCss();
    expect(theme).toContain("--color-*: initial;");
    expect(theme).toContain("--color-text-muted: var(--hx-color-text-muted);");
    expect(tailwindPreset.theme.colors.primary).toBe("var(--hx-color-primary)");
  });

  it("avoids gaudy styling: no gradients and no gold-saturated fills", () => {
    const all = JSON.stringify(colors);
    expect(all).not.toMatch(/gradient/i);
    // The accent is a muted bronze: saturation stays low.
    const [r, g, b] = [0, 2, 4].map((i) => Number.parseInt(colors.light.accent.slice(1 + i, 3 + i), 16) / 255) as [number, number, number];
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const lightness = (max + min) / 2;
    const saturation = max === min ? 0 : (max - min) / (1 - Math.abs(2 * lightness - 1));
    expect(saturation).toBeLessThan(0.5);
  });
});
