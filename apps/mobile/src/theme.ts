/** Design tokens, read from the same file the guest page reads.
 *
 * A group sees both surfaces: the organiser works in the app, the friend opens
 * a link. Two hand-maintained palettes would drift, and one green in the app
 * against a different green in the link makes it look like two products.
 */
import { TextStyle, useColorScheme } from "react-native";
import tokens from "../../../packages/shared/tokens.json";

export type Palette = typeof tokens.color.light;

const { _: _radiusDoc, ...radiusScale } = tokens.radius;
export const radius = radiusScale;

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? tokens.color.dark : tokens.color.light;
}

/** Spacing scale, read from tokens.json rather than retyped here.
 *
 * It was a second hand-maintained copy of the same six numbers, which is the
 * exact drift this file's header warns about: the web scale could move and the
 * app would keep its own. `space.xxl` now exists because the shared scale has
 * it, not because a screen asked for it. */
const { _: _spaceDoc, ...spaceScale } = tokens.space;
export const space = spaceScale;

// Typed as TextStyle rather than `as const`. The const assertion made
// `fontVariant` a readonly tuple, which React Native's TextStyle does not
// accept, so every <Text style={type.amount}> was a type error. Caught the
// first time this app was ever typechecked.
//
// Sizes and weights come from tokens.json so the app and the guest page cannot
// drift apart. The app's names are its own: `amount` is what a money screen
// calls the display step, and `amountSmall` is an app-only step with no web
// counterpart, so it stays a literal rather than being forced onto a token
// that does not mean the same thing.
const t = tokens.type;
const w = (weight: string) => weight as TextStyle["fontWeight"];

export const type: Record<
  "amount" | "amountSmall" | "title" | "body" | "label" | "micro",
  TextStyle
> = {
  /** Tabular figures matter anywhere a column of money is read down. */
  amount: {
    fontSize: t.display.size,
    fontWeight: w(t.display.weight),
    letterSpacing: t.display.tracking,
    fontVariant: ["tabular-nums"],
  },
  amountSmall: { fontSize: 17, fontWeight: "600", fontVariant: ["tabular-nums"] },
  title: {
    fontSize: t.title.size,
    fontWeight: w(t.title.weight),
    letterSpacing: t.title.tracking,
  },
  body: { fontSize: t.body.size, fontWeight: w(t.body.weight) },
  label: { fontSize: t.label.size, fontWeight: w(t.label.weight) },
  micro: {
    fontSize: t.micro.size,
    fontWeight: w(t.micro.weight),
    letterSpacing: t.micro.tracking,
  },
};
