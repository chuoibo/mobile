/** Design tokens, read from the same file the guest page reads.
 *
 * A group sees both surfaces: the organiser works in the app, the friend opens
 * a link. Two hand-maintained palettes would drift, and one green in the app
 * against a different green in the link makes it look like two products.
 */
import { useColorScheme } from "react-native";
import tokens from "../../../packages/shared/tokens.json";

export type Palette = typeof tokens.color.light;

export const radius = tokens.radius;

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? tokens.color.dark : tokens.color.light;
}

/** Spacing scale. Four steps, no more, so screens stay on one rhythm. */
export const space = { xs: 6, sm: 10, md: 16, lg: 24, xl: 36 } as const;

export const type = {
  /** Tabular figures matter anywhere a column of money is read down. */
  amount: { fontSize: 34, fontWeight: "700", letterSpacing: -1, fontVariant: ["tabular-nums"] },
  amountSmall: { fontSize: 17, fontWeight: "600", fontVariant: ["tabular-nums"] },
  title: { fontSize: 20, fontWeight: "600", letterSpacing: -0.3 },
  body: { fontSize: 16, fontWeight: "400" },
  label: { fontSize: 13, fontWeight: "400" },
} as const;
