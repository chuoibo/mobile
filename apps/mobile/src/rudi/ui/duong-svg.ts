/**
 * Path data for the kit's own SVG shapes, kept free of React so the grammar
 * can be run on node.
 *
 * react-native-svg parses `d` in Java (`PathParser`) at MOUNT time. One stray
 * token -- an `L` with no numbers, a `NaN`, an exponent -- throws
 * `IllegalArgumentException` inside Fabric's mount loop and the whole app dies
 * on its first frame, before any screen is visible. Neither tsc nor the web
 * export sees it: browsers tolerate a truncated path and draw what they can.
 * The 2026-09-05 board went red on every flow for exactly this, from a torn
 * tape edge whose last segment was `L Z`. So every builder here returns
 * explicit commands with a fixed arity and plain decimal numbers, and
 * `tests/duong-svg.test.mjs` parses what they return the way the Java side does.
 */

/** Plain decimal, never exponent notation, never `-0`. */
function so(n: number): string {
  const s = n.toFixed(2).replace(/\.?0+$/, "");
  return s === "-0" ? "0" : s;
}

/**
 * Outline of a strip of tape torn at both ends: straight top and bottom edges,
 * a jagged step edge on the left and right. The wobble is a fixed function of
 * the row and the width so two tapes of different widths tear differently and
 * the same tape tears the same way on every render (no flicker on re-layout).
 */
export function duongWashiXeMep(w: number, h: number): string {
  const step = 4;
  const inset = 6;
  const wobble = (y: number, dir: 1 | -1) => ((Math.round(y) * 7 + Math.round(w)) % 3) * 1.6 * dir;
  const parts: string[] = [`M ${so(inset)} 0`, `L ${so(w - inset)} 0`];
  // right torn end, top to bottom
  for (let y = 0; y <= h; y += step) parts.push(`L ${so(w - inset + wobble(y, 1))} ${so(y)}`);
  parts.push(`L ${so(w - inset)} ${so(h)}`, `L ${so(inset)} ${so(h)}`);
  // left torn end, bottom to top
  for (let y = Math.floor(h / step) * step; y >= 0; y -= step) parts.push(`L ${so(inset + wobble(y, -1))} ${so(y)}`);
  parts.push("Z");
  return parts.join(" ");
}

export interface DuongCongS {
  d: string;
  /** Point on the curve at parameter t in [0, 1]; stops are placed with it. */
  diem: (t: number) => { x: number; y: number };
}

/** One cubic S-curve across a `w`×`h` box, read left-to-right; flipped for "up". */
export function duongCongS(w: number, h: number, direction: "down" | "up" = "down"): DuongCongS {
  const p = direction === "down"
    ? { x0: w * 0.08, y0: h * 0.12, c1x: w * 0.9, c1y: h * 0.02, c2x: w * 0.05, c2y: h * 0.75, x1: w * 0.92, y1: h * 0.9 }
    : { x0: w * 0.08, y0: h * 0.9, c1x: w * 0.9, c1y: h * 0.98, c2x: w * 0.05, c2y: h * 0.25, x1: w * 0.92, y1: h * 0.12 };
  const d = `M ${so(p.x0)} ${so(p.y0)} C ${so(p.c1x)} ${so(p.c1y)} ${so(p.c2x)} ${so(p.c2y)} ${so(p.x1)} ${so(p.y1)}`;
  const diem = (t: number) => {
    const mt = 1 - t;
    return {
      x: mt ** 3 * p.x0 + 3 * mt ** 2 * t * p.c1x + 3 * mt * t ** 2 * p.c2x + t ** 3 * p.x1,
      y: mt ** 3 * p.y0 + 3 * mt ** 2 * t * p.c1y + 3 * mt * t ** 2 * p.c2y + t ** 3 * p.y1,
    };
  };
  return { d, diem };
}

/** Sheen line along the top of a tape. */
export function duongVachSang(w: number, y = 1.5, inset = 8): string {
  return `M ${so(inset)} ${so(y)} L ${so(w - inset)} ${so(y)}`;
}
