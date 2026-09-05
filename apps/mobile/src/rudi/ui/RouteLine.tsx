import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

import { duongCongS } from "./duong-svg";

export interface RouteLineProps {
  width: number;
  height: number;
  /** Ink of the line and its stops. */
  color: string;
  /** Number of stops drawn along the route, 2–5. */
  stops?: number;
  /** Which stop is where the group is now (filled); the others stay hollow. Default: the last. */
  activeStop?: number;
  /** Pencil plan (dashed) or ink (solid, default). */
  dashed?: boolean;
  /** Where the pen starts: the route reads left-to-right, top-to-bottom. */
  direction?: "down" | "up";
  opacity?: number;
  accessibilityLabel?: string;
  /**
   * One Ionicons glyph per stop: what each stop MEANS, so the route reads as a
   * plan with places on it, not as a diagram of circles. Needs one per stop.
   */
  glyphs?: readonly (keyof typeof Ionicons.glyphMap)[];
  /** Fill of the stop the group is at (the tape's coral on the cover); default the ink. */
  activeColor?: string;
  /** Glyph colour on the active fill (dark ink on coral); default the ink. */
  activeInk?: string;
}

/**
 * One continuous ink route with a few stops: the journal's plan motif.
 *
 * It appears wherever the product talks about a night out as a sequence --
 * the cover, an outing's timeline, an empty plan -- drawn by the same pen so
 * every screen recognises it. A gentle S-curve, dashed like a pencil plan
 * when `dashed`, solid ink otherwise, with ringed stops; the filled stop is
 * where the group is now, so a pager can advance it one stop per page. With
 * `glyphs`, each stop carries its meaning and the active one is a coral seal.
 */
export function RouteLine({
  width,
  height,
  color,
  stops = 3,
  activeStop,
  dashed = false,
  direction = "down",
  opacity = 1,
  accessibilityLabel,
  glyphs,
  activeColor,
  activeInk,
}: RouteLineProps) {
  const n = Math.min(5, Math.max(2, stops));
  const w = width, h = height;
  // Path grammar lives in `duong-svg.ts`, where node can parse it the way the Java side does.
  const { d, diem: point } = duongCongS(w, h, direction);
  const withGlyphs = !!glyphs && glyphs.length >= n;
  const r = withGlyphs ? 16 : Math.max(5, Math.min(8, w / 44));
  const rActive = r + (withGlyphs ? 5 : 2);
  const active = activeStop === undefined ? n - 1 : Math.min(n - 1, Math.max(0, activeStop));
  const fillActive = activeColor ?? color;
  const inkActive = activeInk ?? color;
  return (
    <View
      accessibilityLabel={accessibilityLabel}
      accessibilityRole={accessibilityLabel ? "image" : undefined}
      style={{ width: w, height: h, opacity }}
    >
      <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={StyleSheet.absoluteFill}>
        <Path d={d} stroke={color} strokeWidth={3} {...(dashed ? { strokeDasharray: "7 7" } : {})} strokeLinecap="round" fill="none" />
        {Array.from({ length: n }, (_, i) => {
          const q = point(i / (n - 1));
          const here = i === active;
          return (
            <Circle
              key={i}
              cx={q.x}
              cy={q.y}
              r={here ? rActive : r}
              fill={here ? fillActive : "transparent"}
              stroke={color}
              strokeWidth={here ? 3 : 2.5}
            />
          );
        })}
      </Svg>
      {withGlyphs
        ? Array.from({ length: n }, (_, i) => {
            const q = point(i / (n - 1));
            const here = i === active;
            const size = here ? 20 : 15;
            return (
              <View key={i} pointerEvents="none" style={[styles.glyph, { left: q.x - size, top: q.y - size, width: size * 2, height: size * 2 }]}>
                <Ionicons color={here ? inkActive : color} name={glyphs[i]} size={size} />
              </View>
            );
          })
        : null}
    </View>
  );
}

const styles = StyleSheet.create({
  glyph: { position: "absolute", alignItems: "center", justifyContent: "center" },
});
