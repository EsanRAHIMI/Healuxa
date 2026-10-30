/**
 * Local design tokens (light + dark). Swappable for `@healuxa/design-tokens` once it lands.
 * Colour pairs meet WCAG AA contrast for body text on their surfaces.
 */
import { useColorScheme } from 'react-native';

const palette = {
  ivory: '#F7F4EF',
  sand: '#EDE6DC',
  bronze: '#8C6A43',
  bronzeDark: '#6E5233',
  bronzeLight: '#C9A57A',
  ink: '#1C1915',
  inkSoft: '#5B544B',
  night: '#14110F',
  nightRaised: '#211D19',
  nightLine: '#3A332C',
  mist: '#E8E2D9',
  mistSoft: '#B5ACA0',
  success: '#2F6B4F',
  successDark: '#7BC7A0',
  danger: '#A3362B',
  dangerDark: '#F08B7F',
  white: '#FFFFFF',
};

export interface Theme {
  dark: boolean;
  color: {
    background: string;
    surface: string;
    surfaceAlt: string;
    border: string;
    text: string;
    textMuted: string;
    accent: string;
    onAccent: string;
    success: string;
    danger: string;
  };
  space: (n: number) => number;
  radius: { sm: number; md: number; lg: number; pill: number };
  font: { title: number; heading: number; body: number; small: number; caption: number };
}

const base = {
  space: (n: number) => n * 4,
  radius: { sm: 8, md: 12, lg: 20, pill: 999 },
  font: { title: 30, heading: 20, body: 16, small: 14, caption: 12 },
};

export const lightTheme: Theme = {
  ...base,
  dark: false,
  color: {
    background: palette.ivory,
    surface: palette.white,
    surfaceAlt: palette.sand,
    border: '#DDD4C7',
    text: palette.ink,
    textMuted: palette.inkSoft,
    accent: palette.bronzeDark,
    onAccent: palette.white,
    success: palette.success,
    danger: palette.danger,
  },
};

export const darkTheme: Theme = {
  ...base,
  dark: true,
  color: {
    background: palette.night,
    surface: palette.nightRaised,
    surfaceAlt: '#2A251F',
    border: palette.nightLine,
    text: palette.mist,
    textMuted: palette.mistSoft,
    accent: palette.bronzeLight,
    onAccent: palette.night,
    success: palette.successDark,
    danger: palette.dangerDark,
  },
};

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? darkTheme : lightTheme;
}
