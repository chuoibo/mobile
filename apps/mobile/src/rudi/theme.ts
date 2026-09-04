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

// ---- Colours that are not scheme tokens --------------------------------------
// `tests/rudi-khong-hex.test.mjs` lets only this file spell a colour. What follows
// is fixed by the artwork it sits on (ink on a photo, a scrim over a gradient, the
// printed receipt of the fixture) or is the fixture-only badge palette; none of it
// follows the colour scheme, which is why it is not in tokens.json.

/** The light palette as static values, for artwork that never switches scheme. */
export const mauSang = tokens.color.light;
/** Brand tier (glow / coral / rose / violet); large areas only, never under small text. */
export const mauThuongHieu = tokens.brand;
/** Ink on photos, gradients and tone fills. */
export const mucTrenAnh = "#FFFFFF";
/** Ground of an image slot before the photo arrives. */
export const nenAnhTrong = "#E7DACE";
export const bongDen = "#000000";
export const mauLogo = { diem: "#FF9F1C" };
export const mauSao = { dam: "#F59E0B", sang: "#FBBF24" };
/** The printed receipt drawn by the fixture bill screen. */
export const giayHoaDon = {
  nen: ["#FFFDF7", "#F4E8D7", "#FFF9EC"] as const,
  khung: "#4A2818",
  bong: "#1B0902",
  bongNau: "#491C06",
  vien: "#D1BCA0",
  chuDam: "#241D18",
  chuVua: "#302923",
  chuNhat: "#453B34",
  chuMo: "#51463E",
};
/** Badge and category colours of the fixture world only (dev door). */
export const bangMauFixture = {
  cam: "#F97316",
  camDam: "#EA580C",
  vangSam: "#A16207",
  xanhLa: "#16A34A",
  xanhLaNhat: "#65A30D",
  xanhTroi: "#0EA5E9",
  xanhBien: "#0891B2",
  xanhDam: "#2563EB",
  hong: "#EC4899",
  hongDam: "#DB2777",
  do: "#E11D48",
  doHong: "#E85D75",
  ngoc: "#0D9488",
  ngocDam: "#0F766E",
  luc: "#10B981",
  than: "#1F2230",
};

/** `#rrggbb` + alpha -> `rgba()`; the only place a colour is composed at runtime. */
export function phuMau(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1, 7), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/** Scrims: white over photos, warm near-black over gradients, neutral for glass sheets. */
export const lopPhu = {
  trang: (alpha: number) => phuMau(mucTrenAnh, alpha),
  toi: (alpha: number) => phuMau("#140803", alpha),
  xam: (alpha: number) => phuMau("#0F0C0A", alpha),
};
