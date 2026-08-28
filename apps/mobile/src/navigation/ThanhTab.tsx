/** The five-slot bar along the bottom, with the create button in the middle.
 *
 * The middle slot is not a tab and is not drawn like one: it is raised out of
 * the bar, filled with the action gradient, and it never takes the selected
 * state. Pressing it opens a menu and leaves you on the screen you were on,
 * which is the behaviour the mockup implies by making it a floating button
 * rather than a fifth icon.
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
  const left = TABS.slice(0, 2);
  const right = TABS.slice(2);

  return (
    <View
      accessibilityRole="tablist"
      style={{
        flexDirection: "row",
        alignItems: "flex-start",
        backgroundColor: c.card,
        borderTopColor: c.line,
        borderTopWidth: 1,
        paddingTop: space.sm,
        paddingBottom: BOTTOM_INSET,
      }}
    >
      {left.map((t) => (
        <TabSlot
          key={t.id}
          id={t.id}
          label={t.label}
          a11yLabel={t.a11yLabel}
          selected={active === t.id}
          onPress={() => onSelect(t.id)}
        />
      ))}

      <NutTao onPress={onCreate} open={menuOpen} />

      {right.map((t) => (
        <TabSlot
          key={t.id}
          id={t.id}
          label={t.label}
          a11yLabel={t.a11yLabel}
          selected={active === t.id}
          onPress={() => onSelect(t.id)}
        />
      ))}
    </View>
  );
}

function TabSlot({ id, label, a11yLabel, selected, onPress }: {
  id: string;
  label: string;
  a11yLabel: string;
  selected: boolean;
  onPress: () => void;
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
      accessibilityState={{ selected }}
      style={({ pressed }) => ({
        flex: 1,
        minHeight: 44,
        alignItems: "center",
        justifyContent: "center",
        gap: 3,
        opacity: pressed ? 0.6 : 1,
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

/** The raised create button. Same footprint as a tab slot, different job. */
function NutTao({ onPress, open }: { onPress: () => void; open: boolean }) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, alignItems: "center" }}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={open ? "Đóng menu tạo mới" : "Tạo mới"}
        accessibilityState={{ expanded: open }}
        style={({ pressed }) => ({
          width: 54,
          height: 54,
          borderRadius: radius.pill,
          // Lifted above the bar's top edge, as in the mockup.
          marginTop: -22,
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
    </View>
  );
}
