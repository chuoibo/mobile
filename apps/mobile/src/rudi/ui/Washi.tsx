import { useState, type ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Path } from "react-native-svg";

import { phuMau, useRudiTheme, type RudiTone } from "../theme";
import { duongVachSang, duongWashiXeMep } from "./duong-svg";

export interface WashiProps {
  tone?: RudiTone;
  /** A hair of rotation, like tape laid by hand. */
  tilt?: -2 | -1 | 0 | 1 | 2;
  height?: number;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
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
          <Path d={duongWashiXeMep(width, height)} fill={fill} fillOpacity={0.9} />
          <Path d={duongVachSang(width)} stroke={phuMau(colors.card, 0.35)} strokeWidth={1.5} />
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
