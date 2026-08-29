/** The five-slot bar along the bottom, with the create button in the middle.
 *
 * The middle slot is not a tab and is not drawn like one: it is raised out of
 * the bar, filled with the action gradient, and it never takes the selected
 * state. Pressing it opens a menu and leaves you on the screen you were on,
 * which is the behaviour the mockup implies by making it a floating button
 * rather than a fifth icon.
 *
 * ## Why [+] is not inside the tablist
 *
 * It used to be: `role="tablist"` sat on the whole bar and owned five
 * children, the middle one a wrapper `<div>` with no role and no name. That is
 * `aria-required-children`, critical -- a screen reader entering the app's
 * main navigation met an element that was neither a tab nor anything else, and
 * the whole tablist was invalid because of it. Giving [+] `role="tab"` would
 * have silenced axe and lied: pressing it does not change tab.
 *
 * So the role moved down onto a row that holds exactly the four tabs, and [+]
 * became a sibling of that row, positioned over the gap the tabs leave for it.
 * The geometry is deliberately unchanged: the two inner tabs carry a 10 %
 * margin each, so the four `flex: 1` tabs share the remaining 80 % and sit at
 * 10 / 30 / 70 / 90 % exactly as they did when there were five equal slots.
 *
 * The bar's own padding moved onto that row for the same reason. An absolutely
 * positioned child is offset by the parent's padding in Yoga and is not in
 * CSS, so a padded parent would have put [+] in two different places on native
 * and on web; a parent with no padding cannot.
 */
import React from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../theme";
import { ACTION_RAMP, Gradient } from "./Gradient";
import {
  IconCaNhan,
  IconKhamPha,
  IconLenPlan,
  IconPlus,
  IconTinNhan,
  type IconProps,
} from "./icons";
import { TABS } from "./tabs";

const GLYPHS: Record<string, (p: IconProps) => React.ReactElement> = {
  "kham-pha": IconKhamPha,
  "len-plan": IconLenPlan,
  "tin-nhan": IconTinNhan,
  "ca-nhan": IconCaNhan,
};

/** Bottom inset. The app does not depend on react-native-safe-area-context, and
 *  a bar flush with the home indicator is a bar you cannot press the edge of. */
const BOTTOM_INSET = Platform.OS === "ios" ? 22 : 12;

export function ThanhTab({ active, onSelect, onCreate, menuOpen }: {
  active: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
  menuOpen: boolean;
}) {
  const c = usePalette();

  return (
    <View
      style={{
        flexDirection: "row",
        backgroundColor: c.card,
        borderTopColor: c.line,
        borderTopWidth: 1,
      }}
    >
      <View
        accessibilityRole="tablist"
        style={{
          flex: 1,
          flexDirection: "row",
          alignItems: "flex-start",
          paddingTop: space.sm,
          paddingBottom: BOTTOM_INSET,
        }}
      >
        {TABS.map((t, i) => (
          <TabSlot
            key={t.id}
            id={t.id}
            label={t.label}
            a11yLabel={t.a11yLabel}
            selected={active === t.id}
            onPress={() => onSelect(t.id)}
            // The hole [+] sits in. Half of a five-slot width on each of the
            // two inner tabs, which leaves the other four where they were.
            gap={i === 1 ? "right" : i === 2 ? "left" : null}
          />
        ))}
      </View>

      <NutTao onPress={onCreate} open={menuOpen} />
    </View>
  );
}

/** Half the width of the slot [+] occupies, as a share of the bar: five equal
 *  slots is what the mockup draws, so the hole is one of them, and each of the
 *  two inner tabs carries half of it. 100 / 5 / 2, written out rather than
 *  computed -- a template literal ending in `}%` is what the percentage gate in
 *  `receipt.test.mjs` looks for, and it only pardons one written directly on a
 *  layout property. A standalone const is not that, and the gate is right to
 *  say so rather than be widened for a caller. */
const HALF_SLOT = "10%";

function TabSlot({ id, label, a11yLabel, selected, onPress, gap }: {
  id: string;
  label: string;
  a11yLabel: string;
  selected: boolean;
  onPress: () => void;
  gap: "left" | "right" | null;
}) {
  const c = usePalette();
  const Glyph = GLYPHS[id];
  // Selected is `accent`, measured 5.16:1 on card. Unselected is `inkSoft` at
  // 7.49:1 -- deliberately not `inkFaint`, because an unselected tab is still
  // a control someone has to read to know where they are.
  const tone = selected ? c.accent : c.inkSoft;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="tab"
      accessibilityLabel={a11yLabel}
      // `aria-selected`, not `accessibilityState={{ selected }}`.
      // react-native-web 0.21 handles no prop by that name at all -- grep its
      // createDOMProps for `accessibilityState` and the answer is zero -- so
      // the state was dropped before it reached the DOM and all four tabs read
      // identically to a screen reader, with nothing saying which one you are
      // on. This is not a web-only spelling: React Native's own Pressable
      // resolves `ariaSelected ?? accessibilityState?.selected`, so one prop
      // now serves both platforms.
      aria-selected={selected}
      style={({ pressed }) => ({
        flex: 1,
        minHeight: 44,
        alignItems: "center",
        justifyContent: "center",
        gap: 3,
        opacity: pressed ? 0.6 : 1,
        marginLeft: gap === "left" ? HALF_SLOT : undefined,
        marginRight: gap === "right" ? HALF_SLOT : undefined,
      })}
    >
      <Glyph color={tone} size={23} />
      <Text
        style={{
          ...type.micro,
          color: tone,
          // Weight, not colour alone, carries the selection. Colour alone
          // fails anyone who cannot separate orange from grey.
          fontWeight: selected ? "700" : "500",
        }}
        numberOfLines={1}
      >
        {label}
      </Text>
    </Pressable>
  );
}

/** The raised create button, centred over the hole the four tabs leave.
 *
 * No wrapper: the `Pressable` *is* the absolutely positioned element, so it
 * covers its own 54 px and nothing else. A full-width wrapper would have sat
 * on top of the bar and eaten presses meant for the tabs on web, where a plain
 * `<div>` intercepts clicks even with no handler on it.
 */
const SIZE = 54;

function NutTao({ onPress, open }: { onPress: () => void; open: boolean }) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={open ? "Đóng menu tạo mới" : "Tạo mới"}
      // Same substitution as the tabs above, same reason: `expanded` inside
      // `accessibilityState` reached the DOM as nothing, so the button read
      // the same closed as open.
      aria-expanded={open}
      style={({ pressed }) => ({
        position: "absolute",
        left: "50%",
        marginLeft: -SIZE / 2,
        // Where `marginTop: -22` used to put it: the bar's own padding, minus
        // the lift, measured from inside the top border. The bar itself is
        // unpadded so this offset means the same thing on both platforms.
        top: space.sm - 22,
        width: SIZE,
        height: SIZE,
        borderRadius: radius.pill,
        overflow: "hidden",
        alignItems: "center",
        justifyContent: "center",
        transform: [{ scale: pressed ? 0.94 : 1 }],
        // A ring in the bar's own colour separates the button from the bar
        // without inventing a shadow token.
        borderWidth: 3,
        borderColor: c.card,
      })}
    >
      <Gradient
        colors={ACTION_RAMP}
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
      />
      <IconPlus color={c.accentInk} size={26} open={open} />
    </Pressable>
  );
}
