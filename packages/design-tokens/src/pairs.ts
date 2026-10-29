import type { SemanticColors } from "./tokens.ts";

export interface ContrastPair {
  fg: keyof SemanticColors;
  bg: keyof SemanticColors;
  /** 4.5 for body text (SC 1.4.3), 3 for UI component boundaries / focus indicators (SC 1.4.11). */
  min: 4.5 | 3;
  usage: string;
}

/** Every foreground/background combination components are allowed to use. Verified by test. */
export const contrastPairs: ContrastPair[] = [
  ...(["bg", "surface", "surfaceMuted", "surfaceRaised"] as const).flatMap((bg) => [
    { fg: "text" as const, bg, min: 4.5 as const, usage: "body text" },
    { fg: "textMuted" as const, bg, min: 4.5 as const, usage: "secondary text" },
    { fg: "primary" as const, bg, min: 4.5 as const, usage: "links, text buttons" },
    { fg: "accent" as const, bg, min: 4.5 as const, usage: "accent labels" },
    { fg: "success" as const, bg, min: 4.5 as const, usage: "success text" },
    { fg: "warning" as const, bg, min: 4.5 as const, usage: "warning text" },
    { fg: "danger" as const, bg, min: 4.5 as const, usage: "error text" },
    { fg: "info" as const, bg, min: 4.5 as const, usage: "info text" },
    { fg: "borderStrong" as const, bg, min: 3 as const, usage: "input borders" },
    { fg: "focus" as const, bg, min: 3 as const, usage: "focus ring" },
  ]),
  { fg: "onPrimary", bg: "primary", min: 4.5, usage: "primary button label" },
  { fg: "onPrimary", bg: "primaryHover", min: 4.5, usage: "primary button hover label" },
  { fg: "onPrimarySoft", bg: "primarySoft", min: 4.5, usage: "selected chip / badge" },
  { fg: "onAccentSoft", bg: "accentSoft", min: 4.5, usage: "accent badge" },
  { fg: "onSuccessSoft", bg: "successSoft", min: 4.5, usage: "success alert" },
  { fg: "onWarningSoft", bg: "warningSoft", min: 4.5, usage: "warning alert" },
  { fg: "onDangerSoft", bg: "dangerSoft", min: 4.5, usage: "error alert" },
  { fg: "onInfoSoft", bg: "infoSoft", min: 4.5, usage: "info alert" },
  { fg: "text", bg: "primarySoft", min: 4.5, usage: "body text in tinted panels" },
  { fg: "text", bg: "accentSoft", min: 4.5, usage: "body text in accent panels" },
];
