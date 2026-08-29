/** Toggle state that actually survives the trip to the DOM.
 *
 * `accessibilityState={{ checked }}` is the React Native spelling of "this box
 * is ticked", and on web it delivers nothing at all. react-native-web 0.21.2
 * forwards no prop by that name: grepping its shipped `dist` for
 * `accessibilityState` returns five hits, all inside the deprecated
 * `TouchableWithoutFeedback` prop map and `isDisabled`, none on the path
 * `Pressable` and `View` take. Rendered through the real library, a cell that
 * declared the state came out as
 *
 *     <div role="checkbox" tabindex="0" class="...">
 *
 * byte-identical ticked and unticked. A screen reader announced "checkbox" and
 * never said whether it was on, and pressing it announced nothing, on the very
 * cells that decide how much each person owes.
 *
 * `aria-checked` is not a web-only spelling of the same idea. React Native's
 * own `Pressable` and `View` resolve `ariaChecked ?? accessibilityState?.checked`
 * (`Libraries/Components/Pressable/Pressable.js:229`), so one prop serves both
 * platforms and sending both would only create two places to disagree.
 *
 * The role travels together with the state on purpose, because picking the
 * attribute is the half people get wrong. `aria-selected` is invalid on `radio`
 * and on `button`; both of the occurrences this module was written for had
 * paired them by hand -- a chip row that said `role="radio"` with
 * `selected`, and a mode switch that said `role="button"` with `selected`.
 * `checkbox`, `radio` and `switch` all take `aria-checked` and nothing else,
 * so a caller that asks for the role cannot pick the wrong attribute.
 */

/** Roles whose on/off state is carried by `aria-checked`. */
export type ToggleRole = "checkbox" | "radio" | "switch";

export type ToggleProps = {
  accessibilityRole: ToggleRole;
  "aria-checked": boolean;
};

/** Spread onto the `Pressable` that is the toggle itself.
 *
 * `on` is required rather than optional: a toggle whose state is unknown is
 * the bug this exists to prevent, so there is no way to ask for the role
 * without also saying which way it is set.
 */
export function toggleState(role: ToggleRole, on: boolean): ToggleProps {
  return { accessibilityRole: role, "aria-checked": on };
}
