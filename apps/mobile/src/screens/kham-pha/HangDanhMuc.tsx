/** The category chips, as one scrolling row under the search box.
 *
 * Mockup: `product/features/02-kham-pha-va-goi-y-dia-diem.png`, screen 1, the
 * strip reading "Quán ăn local · Cafe · Playground · Đi chơi đêm".
 *
 * ## Why this is not `Choice` from the kit
 *
 * `Choice` renders the same idea and is still right everywhere else it is used:
 * a labelled block of options that wraps onto as many lines as it needs. That
 * is the correct shape for a form field, and the wrong one here for two
 * reasons the mockup is explicit about.
 *
 * A wrapping block is a *paragraph* of options: its height changes with the
 * category count, so everything below it -- the section heading, the grid, the
 * map -- moves down when the server adds a fifth category. The mockup pins the
 * grid at a fixed distance from the search box, and the only way to keep that
 * promise is a row of constant height that scrolls sideways instead of growing.
 *
 * And `Choice` prints its label above the options. That is right for a form,
 * where "Danh mục" names a decision the person is being asked to make, and
 * wrong for a browse filter, where the chips are the navigation itself and a
 * heading over them competes with "Gợi ý cho bạn" directly underneath. The
 * label does not disappear, it moves: `aria-label` on the group carries it for
 * anyone who cannot see the chips are chips. Dropping it entirely would leave a
 * screen reader with four unexplained radio buttons.
 *
 * ## The row still scrolls when it does not overflow
 *
 * `horizontal` is unconditional rather than switched on past some width. A
 * conditional would make the row's behaviour depend on the server's category
 * count and on the device width at once, which is two variables deciding one
 * thing and no way to test either. A short row simply never moves.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";

/** Minimum tap target. WCAG 2.2 asks 24x24 and the house floor is the platform
 *  one, 44, which the chips only reached by accident of their font size before.
 *  Stated so a smaller type step later cannot quietly shrink them. */
const CHAM_TOI_THIEU = 44;

export function HangDanhMuc({ options, value, onChange, label = "Danh mục" }: {
  options: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
  /** Named for a screen reader, not drawn. See the header. */
  label?: string;
}) {
  const c = usePalette();
  if (options.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      // Without this the row swallows the first tap on a chip on web, because
      // the scroll view claims the gesture before the Pressable underneath it.
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ gap: space.xs, paddingRight: space.md }}
    >
      <View
        // Same reasoning as `Choice`: the group is what makes "one of these"
        // audible, and axe asks for it as `radio`'s required parent.
        accessibilityRole="radiogroup"
        aria-label={label}
        style={{ flexDirection: "row", gap: space.xs }}
      >
        {options.map((o) => {
          const on = o.id === value;
          return (
            <Pressable
              key={o.id}
              onPress={() => onChange(o.id)}
              {...toggleState("radio", on)}
              style={({ pressed }) => ({
                minHeight: CHAM_TOI_THIEU,
                justifyContent: "center",
                borderWidth: 1,
                // Fully round, unlike the kit's `Choice`. The mockup draws these
                // as pills and the shape is what separates a filter you browse
                // from a field you fill in.
                borderRadius: radius.pill,
                paddingHorizontal: space.md,
                // Unselected has no fill, so the edge is the whole affordance
                // and has to reach 3:1 on the page ground by itself.
                borderColor: on ? c.accent : c.lineStrong,
                backgroundColor: on ? c.accent : "transparent",
                opacity: pressed ? 0.85 : 1,
              })}
            >
              <Text
                numberOfLines={1}
                style={{
                  ...type.body,
                  fontWeight: on ? "600" : "400",
                  color: on ? c.accentInk : c.ink,
                }}
              >
                {o.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}
