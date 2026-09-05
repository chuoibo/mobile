import { useState, type ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Path } from "react-native-svg";

import { phuMau, useRudiTheme, type RudiTone } from "../theme";

export interface WashiProps {
  tone?: RudiTone;
  /** A hair of rotation, like tape laid by hand. */
  tilt?: -2 | -1 | 0 | 1 | 2;
  height?: number;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

/** Torn tape ends: a jagged edge of small steps, seeded per side so no two look alike. */
function tornOutline(w: number, h: number): string {
  const step = 4;
  const jag = (x0: number, dir: 1 | -1) => {
    let d = "";
    for (let y = 0; y <= h; y += step) {
      const wobble = ((y * 7 + w) % 3) * 1.6 * dir;
      d += ` L ${x0 + wobble} ${y}`;
    }
    return d;
  };
  // top edge → right torn end (down) → bottom edge → left torn end (up)
  return `M 6 0 L ${w - 6} 0${jag(w - 6, 1)} L 6 ${h}${jag(6, -1).split(" L ").reverse().join(" L ")} Z`;
}

/**
 * A strip of saturated tape: the one way colour lands on a page at scale.
 * Semi-translucent (0.9) like real washi, torn at both ends, a thin sheen
 * along the top. Used for exactly one region per screen; small text on it is
 * only the tone's own ink (dark ink on coral measures 5.41:1).
 */
export function Washi({ tone = "accent", tilt = 0, height = 30, children, style }: WashiProps) {
  const { brand, colors } = useRudiTheme();
  const fill = tone === "accent" ? brand.coral : tone === "split" ? brand.teal : brand.violet;
  const [width, setWidth] = useState(0);
  return (
    <View
      onLayout={(e) => setWidth(Math.round(e.nativeEvent.layout.width))}
      pointerEvents="box-none"
      style={[styles.strip, { height, ...(tilt === 0 ? {} : { transform: [{ rotate: `${tilt}deg` }] }) }, style]}
    >
      {width > 0 ? (
        <Svg pointerEvents="none" style={StyleSheet.absoluteFill} width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          <Path d={tornOutline(width, height)} fill={fill} fillOpacity={0.9} />
          <Path d={`M 8 1.5 L ${width - 8} 1.5`} stroke={phuMau(colors.card, 0.35)} strokeWidth={1.5} />
        </Svg>
      ) : null}
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { justifyContent: "center", paddingHorizontal: 18, alignSelf: "flex-start", minWidth: 120 },
  content: { alignItems: "center", justifyContent: "center" },
});
