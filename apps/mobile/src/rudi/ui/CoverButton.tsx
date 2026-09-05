import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { typography, useRudiTheme } from "../theme";
import { PressScale } from "./PressScale";

export interface CoverButtonProps {
  label: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * The quiet action on the indigo cover: no fill, so the border is the whole
 * affordance and it is drawn with `coverLineStrong`, the one token measured
 * ≥ 3:1 against the cover in both schemes (services/api/tests/web/
 * test_contrast_floor.py reads it out of this file). Label in `coverInk`.
 */
export function CoverButton({ label, onPress, icon, disabled, loading, style, testID }: CoverButtonProps) {
  const { colors } = useRudiTheme();
  return (
    <PressScale
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled, busy: !!loading }}
      disabled={disabled || loading}
      haptic="select"
      onPress={onPress}
      testID={testID}
      style={[styles.quiet, { borderColor: colors.coverLineStrong, opacity: disabled ? 0.55 : 1 }, style]}
    >
      <View style={styles.row}>
        <Text style={[typography.label, { color: colors.coverInk }]}>{label}</Text>
        {icon ? <Ionicons color={colors.coverInk} name={icon} size={18} /> : null}
      </View>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  quiet: { minHeight: 50, borderWidth: 1, borderRadius: 14, paddingHorizontal: 18, justifyContent: "center" },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 },
});
