import { Platform, TextStyle, useColorScheme, ViewStyle } from "react-native";

import tokens from "../../../../packages/shared/tokens.json";

export type RudiTone = "accent" | "ai" | "split";
export type RudiPalette = typeof tokens.color.light;

export function useRudiTheme() {
  const scheme = useColorScheme();
  const dark = scheme === "dark";
  const colors = dark ? tokens.color.dark : tokens.color.light;

  return {
    dark,
    colors,
    brand: tokens.brand,
    radius: tokens.radius,
    space: tokens.space,
  };
}

export const typography = {
  display: {
    fontSize: 34,
    lineHeight: 39,
    fontWeight: "800",
    letterSpacing: -1.1,
  } satisfies TextStyle,
  h1: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    letterSpacing: -0.65,
  } satisfies TextStyle,
  h2: {
    fontSize: 21,
    lineHeight: 27,
    fontWeight: "700",
    letterSpacing: -0.3,
  } satisfies TextStyle,
  title: {
    fontSize: 17,
    lineHeight: 23,
    fontWeight: "700",
    letterSpacing: -0.15,
  } satisfies TextStyle,
  body: {
    fontSize: 16,
    lineHeight: 23,
    fontWeight: "400",
  } satisfies TextStyle,
  label: {
    fontSize: 14,
    lineHeight: 19,
    fontWeight: "600",
  } satisfies TextStyle,
  caption: {
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "600",
  } satisfies TextStyle,
  money: {
    fontSize: 21,
    lineHeight: 27,
    fontWeight: "800",
    fontVariant: ["tabular-nums"],
  } satisfies TextStyle,
};

export const cardShadow: ViewStyle = Platform.select({
  ios: {
    shadowColor: "#5A3014",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 18,
  },
  android: { elevation: 3 },
  default: {
    shadowColor: "#5A3014",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.1,
    shadowRadius: 18,
  },
});

export function toneColor(palette: RudiPalette, tone: RudiTone) {
  return palette[tone];
}

export function toneSoftColor(palette: RudiPalette, tone: RudiTone) {
  if (tone === "accent") return palette.accentSoft;
  if (tone === "ai") return palette.aiSoft;
  return palette.splitSoft;
}
