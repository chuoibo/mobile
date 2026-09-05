import { useFonts } from "expo-font";

/**
 * The one display face of the shell (ADR-0020), loaded at runtime so a face
 * change never needs a native rebuild. Body text stays on the system stack.
 * Family names are the file stems; RN Android resolves `fontFamily` by that
 * exact string, and the weight is baked into each static instance, so the
 * typography entries that use these set `fontWeight: "normal"`.
 */
export const DISPLAY_FONTS = {
  "BricolageGrotesque-ExtraBold": require("../../assets/fonts/BricolageGrotesque-ExtraBold.ttf"),
  "BricolageGrotesque-Bold": require("../../assets/fonts/BricolageGrotesque-Bold.ttf"),
  "BricolageGrotesque-SemiBold": require("../../assets/fonts/BricolageGrotesque-SemiBold.ttf"),
  "BricolageGrotesque-CondensedBold": require("../../assets/fonts/BricolageGrotesque-CondensedBold.ttf"),
} as const;

export type DisplayFont = keyof typeof DISPLAY_FONTS;

/** `[loaded, error]`. The root layout holds the first frame until `loaded`. */
export function useRudiFonts() {
  return useFonts(DISPLAY_FONTS);
}
