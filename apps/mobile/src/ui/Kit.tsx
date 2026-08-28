/** The few primitives every screen shares.
 *
 * Deliberately small. A component library before the screens exist is a
 * guess about what the screens need; four primitives is what four screens
 * actually used.
 */
import React from "react";
import { Pressable, Text, TextInput, View, ViewStyle } from "react-native";
import { Palette, radius, space, type, usePalette } from "../theme";

export function Screen({ title, hint, children, footer }: {
  title: string; hint?: string; children: React.ReactNode; footer?: React.ReactNode;
}) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ gap: space.xs }}>
        {/* `h1`, the step DESIGN.md assigns to a screen title. `title` is
            the card step and sat only 4px above body, so the heading and
            the text under it read as the same size. */}
        <Text style={{ ...type.h1, color: c.ink }}>{title}</Text>
        {hint ? <Text style={{ ...type.label, color: c.inkSoft }}>{hint}</Text> : null}
      </View>
      <View style={{ flex: 1, gap: space.md }}>{children}</View>
      {footer ? <View style={{ gap: space.sm }}>{footer}</View> : null}
    </View>
  );
}

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  const c = usePalette();
  return (
    <View style={[{
      // `line`, not `lineStrong`. A card is a container, not a control, so
      // WCAG 1.4.11 does not reach it and the soft mockup edge stays soft.
      backgroundColor: c.card, borderColor: c.line, borderWidth: 1,
      borderRadius: radius.base, padding: space.md, gap: space.sm,
    }, style]}>{children}</View>
  );
}

export function Button({ label, onPress, tone = "primary", disabled }: {
  label: string; onPress: () => void;
  tone?: "primary" | "split" | "ghost" | "quiet"; disabled?: boolean;
}) {
  const c = usePalette();
  const skin: Record<string, ViewStyle> = {
    primary: { backgroundColor: c.accent, borderColor: c.accent },
    // Teal, and it is not a second brand colour. DESIGN.md's tone rule gives
    // each of the three a meaning, and `split` means money being divided or
    // settled. The bill-reading screens are that flow, and the mockup draws
    // their confirm button teal for the same reason; an orange one there
    // would say "brand action" on a screen whose whole subject is the bill.
    split: { backgroundColor: c.split, borderColor: c.split },
    ghost: { backgroundColor: "transparent", borderColor: c.accent },
    // No fill, so this border is the whole affordance rather than trim.
    // It was `line` at 1.21:1 on the page ground, which WCAG 1.4.11 asks
    // 3:1 of; `lineStrong` is the token that carries a control edge.
    quiet: { backgroundColor: "transparent", borderColor: c.lineStrong },
  };
  // Disabled is a skin, not a wash.
  //
  // This used to be `opacity: 0.4` on the Pressable, which composites the
  // fill and the label together toward whatever is behind them. Measured on
  // the running app it left the label at 1.1:1 -- and both buttons on the
  // first screen are disabled until something is typed, so the app opened
  // on a primary action whose word nobody could read.
  //
  // WCAG 1.4.3 exempts inactive controls, so this was never a conformance
  // failure; it was a product one, on the one button the whole flow starts
  // from.
  //
  // Inert is carried by *form*, not by fading: a flat `line` fill with no
  // edge of its own, against `quiet` enabled, which is unfilled with a
  // crisp `lineStrong` outline, and `primary` enabled, which is saturated
  // accent. Dropping only the edge was tried first and was too weak -- the
  // two states of "Thêm" came out nearly identical side by side.
  //
  // The label stays `inkSoft` on that fill: computed 5.46:1 light and
  // 5.55:1 dark. It reads in both states, which is the whole point; the
  // button says whether it is pressable with its shape.
  const inert: ViewStyle = { backgroundColor: c.line, borderColor: c.line };
  const ink = disabled
    ? c.inkSoft
    : tone === "primary" ? c.accentInk
    : tone === "split" ? c.splitInk
    : tone === "ghost" ? c.accent
    : c.inkSoft;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [{
        borderWidth: 1, borderRadius: radius.base,
        paddingVertical: 14, paddingHorizontal: space.md,
        alignItems: "center",
        opacity: pressed && !disabled ? 0.85 : 1,
      }, disabled ? inert : skin[tone]]}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: ink }}>{label}</Text>
    </Pressable>
  );
}

export function Field({ label, value, onChangeText, keyboardType, placeholder }: {
  label: string; value: string; onChangeText: (t: string) => void;
  keyboardType?: "default" | "number-pad"; placeholder?: string;
}) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      {/* Label above the input, never a placeholder standing in for one:
          the placeholder vanishes the moment someone starts typing. */}
      <Text style={{ ...type.label, color: c.inkSoft }}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        keyboardType={keyboardType ?? "default"}
        placeholder={placeholder}
        // A tone of its own, not `inkSoft`. At `inkSoft` the example "480000"
        // sat at almost the same weight as a typed number, so an empty
        // "Tổng tiền" read as a filled one -- somebody presses "Chia tiền"
        // believing they entered a total.
        //
        // The palette this note used to describe is gone. `inkFaint` was
        // #6f7f79 at 4.21:1 on white, and the note argued that sitting under
        // the 4.5:1 WCAG asks of text was an acceptable trade because the
        // permanent label carries the meaning. The mockup-derived palette
        // moved the token to #676e7b, which measures 5.13:1 on `card` and
        // clears the text floor outright, so there is no trade left to
        // defend. Separation from typed `ink` still holds: 5.13:1 against
        // white versus 15.79:1 for entered text.
        placeholderTextColor={c.inkFaint}
        style={{
          ...type.body, color: c.ink, backgroundColor: c.card,
          // `lineStrong`: an input is a control, and its box is what tells
          // someone where to tap. At `line` that box was 1.37:1 on the card.
          borderColor: c.lineStrong, borderWidth: 1, borderRadius: radius.base,
          paddingHorizontal: space.md, paddingVertical: 12,
        }}
      />
    </View>
  );
}

export function Row({ left, right, muted }: { left: string; right: string; muted?: boolean }) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: space.sm }}>
      <Text style={{ ...type.body, color: muted ? c.inkSoft : c.ink, flexShrink: 1 }}>{left}</Text>
      <Text style={{ ...type.amountSmall, color: muted ? c.inkSoft : c.ink }}>{right}</Text>
    </View>
  );
}

export type { Palette };

/** Pick one of a few people. A free-text field cannot name a person when two
 *  of them are called Nam, so anywhere identity matters this replaces typing. */
export function Choice({ label, options, value, onChange }: {
  label: string;
  options: { id: string; label: string }[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      <Text style={{ ...type.label, color: c.inkSoft }}>{label}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
        {options.length === 0 ? (
          <Text style={{ ...type.body, color: c.inkSoft }}>Nhập tên phía trên trước.</Text>
        ) : null}
        {options.map((o) => {
          const on = o.id === value;
          return (
            <Pressable
              key={o.id}
              onPress={() => onChange(o.id)}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
              style={({ pressed }) => ({
                borderWidth: 1, borderRadius: radius.base,
                paddingVertical: 10, paddingHorizontal: space.md,
                // Unselected has no fill either, so the same rule as the
                // quiet button applies: the edge has to reach 3:1 on its own.
                borderColor: on ? c.accent : c.lineStrong,
                backgroundColor: on ? c.accent : "transparent",
                opacity: pressed ? 0.85 : 1,
              })}
            >
              <Text style={{ ...type.body, fontWeight: on ? "600" : "400", color: on ? c.accentInk : c.ink }}>
                {o.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
