/** Gradients, without adding a dependency to draw them.
 *
 * `tokens.json` already decided what the brand gradients are -- `logoGradient`,
 * `heroGradient`, `actionGradient`, measured off the mockup. What it cannot do
 * is paint them: React Native has no gradient primitive, and the usual answers
 * (`expo-linear-gradient`, `react-native-svg`) are a new native module in the
 * dependency tree and a new row in the lockfile. On a shell whose whole job is
 * to be reachable, a native module that builds on a phone and fails
 * `expo export --platform web` is a bad trade for one background.
 *
 * So: N solid bands, interpolated in sRGB, stacked with `flex: 1`. At 48 bands
 * over a phone screen each band is ~18pt and the seams are not findable by
 * eye. Identical output on web and native, because it is the same twelve lines
 * of layout on both.
 *
 * This lives in `navigation/` rather than `ui/Kit.tsx` deliberately. The design
 * system has one author and it is not this lane. Nothing here *decides* a
 * colour -- the stops are read out of the shared tokens -- it only renders a
 * decision someone else already made and wrote down. If the kit ever wants a
 * gradient primitive, moving this there is the frontend lane's call.
 */
import React from "react";
import { View, ViewStyle } from "react-native";
import tokens from "../../../../packages/shared/tokens.json";

/** How many solid steps stand in for a continuous ramp. */
const BANDS = 48;

type Rgb = [number, number, number];

function parseHex(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

/**
 * Colour at position `t` along a list of evenly spaced stops.
 *
 * Interpolated in plain sRGB. A perceptual space would be more correct in
 * general, but these three stops are all saturated warm-to-violet hues with no
 * near-grey midpoint, which is the case where sRGB's muddy middle actually
 * shows. Here it does not, and the alternative is a colour-space conversion
 * nobody can check by looking at the screen.
 */
function sample(stops: Rgb[], t: number): Rgb {
  if (stops.length === 1) return stops[0];
  const scaled = Math.min(t, 1) * (stops.length - 1);
  const i = Math.min(Math.floor(scaled), stops.length - 2);
  const local = scaled - i;
  const from = stops[i];
  const to = stops[i + 1];
  return [
    Math.round(from[0] + (to[0] - from[0]) * local),
    Math.round(from[1] + (to[1] - from[1]) * local),
    Math.round(from[2] + (to[2] - from[2]) * local),
  ];
}

/** A vertical ramp through `colors`, top to bottom. */
export function Gradient({ colors, style, children }: {
  colors: string[];
  style?: ViewStyle;
  children?: React.ReactNode;
}) {
  const stops = colors.map(parseHex);
  return (
    <View style={[{ overflow: "hidden" }, style]}>
      <View style={StyleSheetAbsoluteFill} pointerEvents="none">
        {Array.from({ length: BANDS }, (_, i) => {
          const [r, g, b] = sample(stops, i / (BANDS - 1));
          return (
            <View key={i} style={{ flex: 1, backgroundColor: `rgb(${r},${g},${b})` }} />
          );
        })}
      </View>
      {children}
    </View>
  );
}

/**
 * A darkening wash over whatever is behind it.
 *
 * The reason this exists is contrast, not mood. `tokens.json` says outright
 * that the brand layer may not carry small text -- white on `coral` #fb693e
 * measures 2.92:1, under even the 3:1 floor for a non-text component -- and a
 * sunset background is exactly a brand-layer surface. Rather than pick a
 * different, duller sunset, the text sits on a wash dark enough to pay for
 * itself, which is what the mockup does too.
 *
 * `alphas` are top-to-bottom, so a legible bottom third under a clean top is
 * `[0, 0.35, 0.72]` and not a uniform veil over the whole illustration.
 */
export function Scrim({ alphas, tint = [15, 8, 20], style }: {
  alphas: number[];
  /** Ink of the wash. Warm-dark by default, to match the cream/ember world. */
  tint?: Rgb;
  style?: ViewStyle;
}) {
  const [r, g, b] = tint;
  return (
    <View style={[StyleSheetAbsoluteFill, style]} pointerEvents="none">
      {Array.from({ length: BANDS }, (_, i) => {
        const t = i / (BANDS - 1);
        const scaled = t * (alphas.length - 1);
        const j = Math.min(Math.floor(scaled), alphas.length - 2);
        const local = scaled - j;
        const a = alphas[j] + (alphas[j + 1] - alphas[j]) * local;
        return (
          <View key={i} style={{ flex: 1, backgroundColor: `rgba(${r},${g},${b},${a})` }} />
        );
      })}
    </View>
  );
}

/** Written out rather than imported: one object, used twice, in one file. */
const StyleSheetAbsoluteFill: ViewStyle = {
  position: "absolute",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
};

/**
 * Blend two colours, `t` of the way from `a` to `b`.
 *
 * Exists so an illustration can have depth without anybody inventing a
 * colour. The rule for this lane is that it uses the design system and does
 * not extend it, and a hand-picked "nice dark plum" for a hillside would be
 * exactly an extension -- one that then drifts from the palette it was eyeballed
 * against. Every tone in the opening illustration is instead a stated fraction
 * between two tokens, so it moves when the tokens move and it can be checked
 * by reading the call rather than by sampling the pixel.
 */
export function mixHex(a: string, b: string, t: number): string {
  const [r, g, bl] = sample([parseHex(a), parseHex(b)], t);
  return `rgb(${r},${g},${bl})`;
}

/** The measured brand ramps, so screens name a token instead of a hex. */
export const HERO_SUNSET = [
  tokens.brand.heroGradient.to,   // violet, high in the sky
  tokens.brand.heroGradient.via,  // rose
  tokens.brand.heroGradient.from, // ember, at the horizon
];

export const ACTION_RAMP = [tokens.brand.actionGradient.from, tokens.brand.actionGradient.to];
