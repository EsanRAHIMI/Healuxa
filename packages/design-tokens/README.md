# @healuxa/design-tokens

Colour (light/dark semantic palette), typography, spacing, radii, elevation and motion tokens.
See `docs/DESIGN_SYSTEM.md` for usage rules.

- TypeScript: `import { colors, typography, spacing, radii, elevation, motion } from "@healuxa/design-tokens"`
  (raw values — use these in React Native `StyleSheet`).
- CSS variables: `@import "@healuxa/design-tokens/tokens.css";` (`--hx-color-*`, `--hx-radius-*`, …;
  dark via `data-theme="dark"` or `prefers-color-scheme`).
- Tailwind v4: `@import "@healuxa/design-tokens/theme.css";` (utilities like `bg-surface`, `text-text-muted`).
- Tailwind v3 / NativeWind preset: `import { tailwindPreset } from "@healuxa/design-tokens/tailwind-preset"`.

`npm test` verifies every allowed foreground/background pair (`src/pairs.ts`) meets WCAG 2.2 AA in
both schemes. After editing tokens run `npm run build -w @healuxa/design-tokens` (CI checks `css/` is current).
