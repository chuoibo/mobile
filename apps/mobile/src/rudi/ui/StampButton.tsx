import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { displayFace, useRudiTheme } from "../theme";
import { PressScale } from "./PressScale";

export interface StampButtonProps {
  label: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  disabled?: boolean;
  /** A hair of rotation, like a seal pressed by hand; 0 in lists and forms. */
  tilt?: -2 | -1 | 0 | 1 | 2;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * The cover's primary action: a coral seal with dark ink lettering.
 *
 * On the indigo cover the page's gradient button reads muddy, and white text
 * on coral measures 2.92:1, so the seal inverts: `brand.coral` fill (5.35:1
 * against the cover, a large area) with `ink` lettering (5.41:1 on coral) in
 * the display face. No border: the fill is the affordance, so nothing here
 * owes the 1.4.11 boundary floor. 56dp tall, spring press, impact haptic.
 */
export function StampButton({ label, onPress, icon = "arrow-forward", disabled, tilt = 0, style, testID }: StampButtonProps) {
  const { brand, colors } = useRudiTheme();
  return (
    <PressScale
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      haptic="impact"
      onPress={onPress}
      pressedScale={0.96}
      testID={testID}
      style={[
        styles.seal,
        {
          backgroundColor: brand.coral,
          shadowColor: colors.cover,
          opacity: disabled ? 0.55 : 1,
          transform: tilt === 0 ? undefined : [{ rotate: `${tilt}deg` }],
        },
        style,
      ]}
    >
      <View style={styles.row}>
        <Text style={[styles.label, { color: colors.ink }]}>{label}</Text>
        {icon ? <Ionicons color={colors.ink} name={icon} size={22} /> : null}
      </View>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  seal: {
    minHeight: 56,
    borderRadius: 16,
    paddingHorizontal: 22,
    justifyContent: "center",
    elevation: 8,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
  },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  label: { fontFamily: displayFace.bold, fontSize: 18, lineHeight: 22, letterSpacing: -0.2 },
});
