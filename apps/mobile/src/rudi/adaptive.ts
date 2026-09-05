/**
 * Size classes for the RuDi shell, one contract for every screen.
 *
 * Before this module the shell had a single breakpoint, `700`, typed by hand in
 * four places (`ui.tsx`, the tab layout, a fixture hero). Each place meant
 * something slightly different by it, and none of them knew about height, so a
 * phone turned sideways was laid out like a tablet and a tablet in split-screen
 * like a phone. The classes below follow the Android window size classes
 * (compact < 600dp, medium 600–839dp, expanded ≥ 840dp) and are computed from
 * the *current window*, never from the device, so rotation and split-screen
 * re-classify on the fly.
 *
 * Pure: `dict` in, `dict` out, no React. `ui/useAdaptiveLayout.ts` is the hook
 * that feeds it the window; this file is compiled for the node tests so the
 * boundaries are measured, not eyeballed.
 */

export type SizeClass = "compact" | "medium" | "expanded";
export type HeightClass = "short" | "regular";

/** Android window size class boundaries, in dp. */
export const SIZE_CLASS_BREAKPOINTS = Object.freeze({
  medium: 600,
  expanded: 840,
});

/** Below this height (dp) a phone is on its side or a sheet is fighting the IME. */
export const SHORT_HEIGHT = 480;

export interface AdaptiveLayout {
  sizeClass: SizeClass;
  heightClass: HeightClass;
  /** Media/grid columns a screen may use for cards and album tiles. */
  columns: 1 | 2 | 3;
  /** Horizontal screen gutter (dp), on the 4pt scale of tokens.json. */
  gutter: 16 | 24 | 36;
  /** Navigation is a left rail instead of a bottom bar. */
  rail: boolean;
  /** A list may show its detail beside it instead of pushing a new screen. */
  twoPane: boolean;
  /** Widest measure a single column of content may take (dp). */
  maxContent: number;
}

export function sizeClassFor(width: number): SizeClass {
  if (!Number.isFinite(width) || width < SIZE_CLASS_BREAKPOINTS.medium) return "compact";
  if (width < SIZE_CLASS_BREAKPOINTS.expanded) return "medium";
  return "expanded";
}

export function heightClassFor(height: number): HeightClass {
  return Number.isFinite(height) && height < SHORT_HEIGHT ? "short" : "regular";
}

/** The whole layout contract for one window size. */
export function layoutFor(width: number, height: number): AdaptiveLayout {
  const sizeClass = sizeClassFor(width);
  const heightClass = heightClassFor(height);
  switch (sizeClass) {
    case "expanded":
      return {
        sizeClass,
        heightClass,
        columns: 3,
        gutter: 36,
        rail: true,
        twoPane: true,
        maxContent: 1200,
      };
    case "medium":
      return {
        sizeClass,
        heightClass,
        columns: 2,
        gutter: 24,
        rail: true,
        // A short medium window (a tablet in landscape split, a foldable half
        // open) has no room for a detail pane beside a list.
        twoPane: heightClass === "regular",
        maxContent: 960,
      };
    default:
      return {
        sizeClass,
        heightClass,
        columns: 1,
        gutter: 16,
        rail: false,
        twoPane: false,
        maxContent: width,
      };
  }
}
