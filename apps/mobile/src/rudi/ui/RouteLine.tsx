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
}

/**
 * One continuous ink route with a few stops: the journal's plan motif.
 *
 * It appears wherever the product talks about a night out as a sequence --
 * the cover, an outing's timeline, an empty plan -- drawn by the same pen so
 * every screen recognises it. A gentle S-curve, dashed like a pencil plan
 * when `dashed`, solid ink otherwise, with ringed stops; the filled stop is
 * where the group is now, so a pager can advance it one stop per page.
 */
export function RouteLine({ width, height, color, stops = 3, activeStop, dashed = false, direction = "down", opacity = 1, accessibilityLabel }: RouteLineProps) {
  const n = Math.min(5, Math.max(2, stops));
  const w = width, h = height;
  // Path grammar lives in `duong-svg.ts`, where node can parse it the way the Java side does.
  const { d, diem: point } = duongCongS(w, h, direction);
  const r = Math.max(5, Math.min(8, w / 44));
  const active = activeStop === undefined ? n - 1 : Math.min(n - 1, Math.max(0, activeStop));
  return (
    <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} opacity={opacity} accessibilityLabel={accessibilityLabel} accessibilityRole={accessibilityLabel ? "image" : undefined}>
      <Path d={d} stroke={color} strokeWidth={3} {...(dashed ? { strokeDasharray: "7 7" } : {})} strokeLinecap="round" fill="none" />
      {Array.from({ length: n }, (_, i) => {
        const q = point(i / (n - 1));
        const here = i === active;
        return <Circle key={i} cx={q.x} cy={q.y} r={here ? r + 2 : r} fill={here ? color : "transparent"} stroke={color} strokeWidth={here ? 3 : 2.5} />;
      })}
    </Svg>
  );
}
