/**
 * Healuxa design tokens — the single source for web (CSS variables / Tailwind) and mobile (raw values).
 *
 * Identity: calm, clinical-grade trust with a quiet premium finish. Deep teal ink carries actions,
 * warm ivory and stone neutrals carry surfaces, and a muted bronze accent is reserved for small
 * highlights (never large fills, never gradients). Every text/background pair used by components is
 * verified to WCAG 2.2 AA in test/contrast.test.ts.
 */

export type ColorScheme = "light" | "dark";

export interface SemanticColors {
  /** Page background. */
  bg: string;
  /** Cards, panels, inputs. */
  surface: string;
  /** Subtle section/alternate rows. */
  surfaceMuted: string;
  /** Raised overlays (menus, dialogs). */
  surfaceRaised: string;
  /** Decorative dividers (not relied on to identify controls). */
  border: string;
  /** Control boundaries (inputs, checkboxes) — 3:1 against surfaces. */
  borderStrong: string;
  text: string;
  textMuted: string;
  /** Text on `primary`. */
  onPrimary: string;
  primary: string;
  primaryHover: string;
  primarySoft: string;
  onPrimarySoft: string;
  accent: string;
  accentSoft: string;
  onAccentSoft: string;
  success: string;
  successSoft: string;
  onSuccessSoft: string;
  warning: string;
  warningSoft: string;
  onWarningSoft: string;
  danger: string;
  dangerSoft: string;
  onDangerSoft: string;
  info: string;
  infoSoft: string;
  onInfoSoft: string;
  focus: string;
  overlay: string;
}

export const colors: Record<ColorScheme, SemanticColors> = {
  light: {
    bg: "#FAF8F5",
    surface: "#FFFFFF",
    surfaceMuted: "#F3EFE9",
    surfaceRaised: "#FFFFFF",
    border: "#E2DBD1",
    borderStrong: "#857C70",
    text: "#1B2427",
    textMuted: "#535E5F",
    onPrimary: "#FFFFFF",
    primary: "#0D5962",
    primaryHover: "#0A4850",
    primarySoft: "#E2EFEE",
    onPrimarySoft: "#0A4850",
    accent: "#86663A",
    accentSoft: "#F4EDE2",
    onAccentSoft: "#5E4624",
    success: "#1D6A44",
    successSoft: "#E4F1E9",
    onSuccessSoft: "#16533A",
    warning: "#8A5800",
    warningSoft: "#FBF0D9",
    onWarningSoft: "#6B4400",
    danger: "#A2282E",
    dangerSoft: "#FBE8E8",
    onDangerSoft: "#861F24",
    info: "#2A5A88",
    infoSoft: "#E6EEF7",
    onInfoSoft: "#214A70",
    focus: "#1A7480",
    overlay: "rgba(14, 20, 22, 0.48)",
  },
  dark: {
    bg: "#0E1416",
    surface: "#151D20",
    surfaceMuted: "#1A2427",
    surfaceRaised: "#1D282B",
    border: "#2B373B",
    borderStrong: "#6F8084",
    text: "#ECE8E2",
    textMuted: "#A8B2B0",
    onPrimary: "#062A2E",
    primary: "#6CC3C4",
    primaryHover: "#8AD3D3",
    primarySoft: "#12353A",
    onPrimarySoft: "#BFE7E6",
    accent: "#D2B48A",
    accentSoft: "#2C251B",
    onAccentSoft: "#E8D3B3",
    success: "#73CF9A",
    successSoft: "#10291C",
    onSuccessSoft: "#A9E5C2",
    warning: "#E8B95A",
    warningSoft: "#2E2410",
    onWarningSoft: "#F2D49A",
    danger: "#F08C8C",
    dangerSoft: "#331718",
    onDangerSoft: "#F7BDBD",
    info: "#8DB8E8",
    infoSoft: "#13233A",
    onInfoSoft: "#BED6F2",
    focus: "#8AD3D3",
    overlay: "rgba(0, 0, 0, 0.6)",
  },
};

/**
 * Typography. Families are CSS custom properties so each platform can bind its own font loading
 * (next/font on web, expo-font on mobile). Arabic and Persian get dedicated families with taller
 * line-height; never letter-space Arabic script.
 */
export const typography = {
  family: {
    sans: "var(--hx-font-sans), ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    serif: "var(--hx-font-serif), ui-serif, Georgia, 'Times New Roman', serif",
    arabic: "var(--hx-font-arabic), 'Geeza Pro', 'Noto Sans Arabic', Tahoma, sans-serif",
    persian: "var(--hx-font-persian), 'Noto Sans Arabic', Tahoma, sans-serif",
    mono: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  },
  /** [font-size rem, line-height] — mobile-first; display sizes scale up at the `md` breakpoint in CSS. */
  scale: {
    xs: ["0.75rem", "1.125rem"],
    sm: ["0.875rem", "1.375rem"],
    base: ["1rem", "1.625rem"],
    lg: ["1.125rem", "1.75rem"],
    xl: ["1.25rem", "1.875rem"],
    "2xl": ["1.5rem", "2rem"],
    "3xl": ["1.875rem", "2.375rem"],
    "4xl": ["2.25rem", "2.75rem"],
    "5xl": ["3rem", "3.5rem"],
  },
  weight: { regular: 400, medium: 500, semibold: 600 },
  tracking: { tight: "-0.015em", normal: "0", wide: "0.04em" },
  /** Extra leading for Arabic-script locales. */
  arabicLineHeightMultiplier: 1.15,
} as const;

/** 4 px base grid (rem values assume a 16 px root). */
export const spacing = {
  "0": "0",
  px: "1px",
  "0.5": "0.125rem",
  "1": "0.25rem",
  "1.5": "0.375rem",
  "2": "0.5rem",
  "3": "0.75rem",
  "4": "1rem",
  "5": "1.25rem",
  "6": "1.5rem",
  "8": "2rem",
  "10": "2.5rem",
  "12": "3rem",
  "16": "4rem",
  "20": "5rem",
  "24": "6rem",
} as const;

export const radii = {
  none: "0",
  sm: "0.375rem",
  md: "0.625rem",
  lg: "0.875rem",
  xl: "1.25rem",
  full: "9999px",
} as const;

/** Soft, low-contrast elevation; dark mode relies on surface steps more than shadow. */
export const elevation = {
  light: {
    none: "none",
    sm: "0 1px 2px rgba(27, 36, 39, 0.06)",
    md: "0 2px 8px rgba(27, 36, 39, 0.07), 0 1px 2px rgba(27, 36, 39, 0.05)",
    lg: "0 12px 32px rgba(27, 36, 39, 0.10), 0 2px 6px rgba(27, 36, 39, 0.05)",
  },
  dark: {
    none: "none",
    sm: "0 1px 2px rgba(0, 0, 0, 0.4)",
    md: "0 2px 10px rgba(0, 0, 0, 0.45)",
    lg: "0 14px 36px rgba(0, 0, 0, 0.55)",
  },
} as const;

export const motion = {
  duration: { instant: "0ms", fast: "120ms", base: "200ms", slow: "320ms" },
  easing: {
    standard: "cubic-bezier(0.2, 0, 0, 1)",
    enter: "cubic-bezier(0, 0, 0, 1)",
    exit: "cubic-bezier(0.3, 0, 1, 1)",
  },
  /** Under prefers-reduced-motion every duration collapses to `instant`. */
  reducedMotion: "instant",
} as const;

export const breakpoints = { sm: "40rem", md: "48rem", lg: "64rem", xl: "80rem" } as const;

/** Minimum interactive target (WCAG 2.2 SC 2.5.8 asks 24 px; we use 44 px for touch comfort). */
export const touchTarget = { min: "2.75rem" } as const;

export const tokens = { colors, typography, spacing, radii, elevation, motion, breakpoints, touchTarget } as const;
export type Tokens = typeof tokens;
