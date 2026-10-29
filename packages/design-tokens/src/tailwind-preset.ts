/**
 * Tailwind preset (v3-style config object) for consumers that use a JS config — e.g. NativeWind on the
 * Expo app, or `@config` in Tailwind v4. Web on Tailwind v4 should prefer the CSS-first theme.css.
 */
import { kebab } from "./css.ts";
import { breakpoints, colors, elevation, motion, radii, spacing, typography } from "./tokens.ts";

const colorMap = Object.fromEntries(
  Object.keys(colors.light).map((k) => [kebab(k), `var(--hx-color-${kebab(k)})`]),
) as Record<string, string>;

export const tailwindPreset = {
  darkMode: ["selector", '[data-theme="dark"]'] as [string, string],
  theme: {
    colors: { transparent: "transparent", current: "currentColor", white: "#ffffff", black: "#000000", ...colorMap } as Record<string, string>,
    spacing: { ...spacing },
    borderRadius: { ...radii },
    fontFamily: Object.fromEntries(Object.entries(typography.family).map(([k, v]) => [k, v.split(", ")])),
    fontSize: Object.fromEntries(
      Object.entries(typography.scale).map(([k, [size, lineHeight]]) => [k, [size, { lineHeight }]]),
    ),
    screens: { ...breakpoints },
    extend: {
      boxShadow: Object.fromEntries(Object.keys(elevation.light).map((k) => [k, `var(--hx-shadow-${k})`])),
      transitionDuration: Object.fromEntries(Object.keys(motion.duration).map((k) => [k, `var(--hx-duration-${k})`])),
      transitionTimingFunction: { ...motion.easing },
    },
  },
};

/** Raw (non-variable) colours for platforms without CSS variables, e.g. React Native StyleSheet. */
export const rawColorPreset = { light: colors.light, dark: colors.dark };

export default tailwindPreset;
