import Svg, { Circle, Path } from "react-native-svg";

export interface RouteLineProps {
  width: number;
  height: number;
  /** Ink of the line and its stops. */
  color: string;
  /** Number of stops drawn along the route, 2–5. */
  stops?: number;
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
 * (the trip is not lived yet), with small ringed stops; the last stop is
 * filled: that is where the evening ends and the bill is split.
 */
export function RouteLine({ width, height, color, stops = 3, direction = "down", opacity = 1, accessibilityLabel }: RouteLineProps) {
  const n = Math.min(5, Math.max(2, stops));
  const w = width, h = height;
  // Control points of one S-curve across the box; flipped for "up".
  const p = direction === "down"
    ? { x0: w * 0.08, y0: h * 0.12, c1x: w * 0.9, c1y: h * 0.02, c2x: w * 0.05, c2y: h * 0.75, x1: w * 0.92, y1: h * 0.9 }
    : { x0: w * 0.08, y0: h * 0.9, c1x: w * 0.9, c1y: h * 0.98, c2x: w * 0.05, c2y: h * 0.25, x1: w * 0.92, y1: h * 0.12 };
  const d = `M ${p.x0} ${p.y0} C ${p.c1x} ${p.c1y}, ${p.c2x} ${p.c2y}, ${p.x1} ${p.y1}`;
  const point = (t: number) => {
    const mt = 1 - t;
    return {
      x: mt ** 3 * p.x0 + 3 * mt ** 2 * t * p.c1x + 3 * mt * t ** 2 * p.c2x + t ** 3 * p.x1,
      y: mt ** 3 * p.y0 + 3 * mt ** 2 * t * p.c1y + 3 * mt * t ** 2 * p.c2y + t ** 3 * p.y1,
    };
  };
  const r = Math.max(4, Math.min(7, w / 48));
  return (
    <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} opacity={opacity} accessibilityLabel={accessibilityLabel} accessibilityRole={accessibilityLabel ? "image" : undefined}>
      <Path d={d} stroke={color} strokeWidth={2} strokeDasharray="7 7" strokeLinecap="round" fill="none" />
      {Array.from({ length: n }, (_, i) => {
        const q = point(i / (n - 1));
        const last = i === n - 1;
        return <Circle key={i} cx={q.x} cy={q.y} r={r} fill={last ? color : "transparent"} stroke={color} strokeWidth={2} />;
      })}
    </Svg>
  );
}
