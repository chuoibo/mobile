import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { displayFace, mauSang, phuMau, useRudiTheme } from "../theme";
import { Grain } from "./Grain";
import { PressScale } from "./PressScale";

export interface StampButtonProps {
  label: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  disabled?: boolean;
  loading?: boolean;
  /** A hair of rotation, like a seal pressed by hand: -1.5 on the cover, 0 in forms. */
  tilt?: -2 | -1.5 | -1 | 0 | 1 | 1.5 | 2;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * The ask, as a rubber stamp pressed into the page.
 *
 * Not a pill: no drop shadow (a stamp sits IN the paper, it does not float),
 * a double ink edge (the outer line the rubber leaves, a fainter inner line
 * where the ink pooled), coral ink whose fill is broken by the ink tile, and
 * a slight tilt on the cover. Lettering is the display face in the static
 * dark ink (`mauSang.ink`, 5.41:1 on coral in either scheme); coral itself is a
 * large area, so the brand tier is allowed.
 * The same stamp is the primary action on Login, so the ask has one language.
 */
export function StampButton({ label, onPress, icon = "arrow-forward", disabled, loading, tilt = 0, style, testID }: StampButtonProps) {
  const { brand } = useRudiTheme();
  // Static dark ink: the seal is coral in both schemes, so its lettering never
  // follows the scheme (the dark scheme's light ink on coral read 2.4:1).
  const muc = mauSang.ink;
  const busy = !!loading;
  return (
    <PressScale
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled, busy }}
      disabled={disabled || busy}
      haptic="impact"
      onPress={onPress}
      pressedScale={0.97}
      testID={testID}
      style={[
        styles.seal,
        {
          backgroundColor: brand.coral,
          borderColor: phuMau(muc, 0.88),
          opacity: disabled ? 0.55 : 1,
          ...(tilt === 0 ? {} : { transform: [{ rotate: `${tilt}deg` }] }),
        },
        style,
      ]}
    >
      {/* Ink, not paper: the sparse paper tile measured flat on coral (stddev 2); this one lands at ~8 levels at 1x, like the cloth. */}
      <Grain material="mucIn" opacity={0.26} />
      <View pointerEvents="none" style={[styles.innerEdge, { borderColor: phuMau(muc, 0.32) }]} />
      <View style={styles.row}>
        {busy ? <ActivityIndicator color={muc} /> : null}
        <Text style={[styles.label, { color: muc }]}>{label}</Text>
        {icon && !busy ? <Ionicons color={muc} name={icon} size={22} /> : null}
      </View>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  seal: {
    minHeight: 56,
    borderRadius: 14,
    borderWidth: 2,
    paddingHorizontal: 22,
    justifyContent: "center",
    overflow: "hidden",
  },
  innerEdge: { position: "absolute", left: 4, right: 4, top: 4, bottom: 4, borderRadius: 10, borderWidth: 1 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  label: { fontFamily: displayFace.bold, fontSize: 18, lineHeight: 22, letterSpacing: 0.2 },
});
