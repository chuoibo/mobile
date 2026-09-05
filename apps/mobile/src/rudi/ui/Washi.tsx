import type { ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { phuMau, useRudiTheme, type RudiTone } from "../theme";

export interface WashiProps {
  tone?: RudiTone;
  /** A hair of rotation, like tape laid by hand. */
  tilt?: -2 | -1 | 0 | 1 | 2;
  /** Height of the strip (dp); content, when given, sits on it. */
  height?: number;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

/**
 * A strip of saturated tape: the one way colour lands on a page at scale.
 *
 * The three tones exist as small chips and buttons everywhere; a washi strip
 * is the same meaning at page scale, used for exactly one region per screen
 * (the third raise of the direction round: colour only where it matters now).
 * The brand tier (glow / coral / teal / violet) is allowed here because the
 * strip is a large area; small text never sits on it unless it is the tone's
 * own `*Ink`.
 */
export function Washi({ tone = "accent", tilt = 0, height = 28, children, style }: WashiProps) {
  const { brand, colors } = useRudiTheme();
  const fill = tone === "accent" ? brand.coral : tone === "split" ? brand.teal : brand.violet;
  return (
    <View
      pointerEvents="box-none"
      style={[
        styles.strip,
        { height, backgroundColor: fill, ...(tilt === 0 ? {} : { transform: [{ rotate: `${tilt}deg` }] }) },
        style,
      ]}
    >
      <View style={[styles.sheen, { backgroundColor: phuMau(colors.card, 0.22) }]} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { justifyContent: "center", paddingHorizontal: 12, overflow: "hidden" },
  sheen: { position: "absolute", left: 0, right: 0, top: 0, height: StyleSheet.hairlineWidth * 3 },
});
