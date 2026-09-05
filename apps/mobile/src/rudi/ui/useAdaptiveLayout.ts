import { useMemo } from "react";
import { useWindowDimensions } from "react-native";

import { layoutFor, type AdaptiveLayout } from "../adaptive";

/**
 * The window's size class, recomputed on rotation and split-screen.
 *
 * Reads `useWindowDimensions` (the window, not the screen) so a foldable half
 * open or an app in split-screen is classified by the space it actually has.
 * Every screen and the tab layout read this one hook instead of comparing
 * `width` to a number of their own.
 */
export function useAdaptiveLayout(): AdaptiveLayout {
  const { width, height } = useWindowDimensions();
  return useMemo(() => layoutFor(width, height), [width, height]);
}
