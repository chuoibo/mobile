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
        <Text style={{ ...type.title, color: c.ink }}>{title}</Text>
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
      backgroundColor: c.card, borderColor: c.line, borderWidth: 1,
      borderRadius: radius.base, padding: space.md, gap: space.sm,
    }, style]}>{children}</View>
  );
}

export function Button({ label, onPress, tone = "primary", disabled }: {
  label: string; onPress: () => void; tone?: "primary" | "ghost" | "quiet"; disabled?: boolean;
}) {
  const c = usePalette();
  const skin: Record<string, ViewStyle> = {
    primary: { backgroundColor: c.accent, borderColor: c.accent },
    ghost: { backgroundColor: "transparent", borderColor: c.accent },
    quiet: { backgroundColor: "transparent", borderColor: c.line },
  };
  const ink = tone === "primary" ? c.accentInk : tone === "ghost" ? c.accent : c.inkSoft;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [{
        borderWidth: 1, borderRadius: radius.base,
        paddingVertical: 14, paddingHorizontal: space.md,
        alignItems: "center",
        opacity: disabled ? 0.4 : pressed ? 0.85 : 1,
      }, skin[tone]]}
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
        // believing they entered a total. Going this faint is affordable only
        // because the label above the field never disappears.
        placeholderTextColor={c.inkFaint}
        style={{
          ...type.body, color: c.ink, backgroundColor: c.card,
          borderColor: c.line, borderWidth: 1, borderRadius: radius.base,
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
                borderColor: on ? c.accent : c.line,
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
