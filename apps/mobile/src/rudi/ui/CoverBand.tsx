import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import type { ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { phuMau, useRudiTheme } from "../theme";
import { Grain } from "./Grain";
import { PressScale } from "./PressScale";

export interface CoverBandProps {
  children: ReactNode;
  /** Bleed past the screen's horizontal padding so the cloth reaches the edges. */
  bleed?: number;
  /** Draw a back chevron in cover ink; `true` pops the router, a function runs instead. */
  onBack?: boolean | (() => void);
  style?: StyleProp<ViewStyle>;
}

/**
 * The notebook's cover as a band at the top of a page: indigo cloth carrying
 * the brand moment (greeting, logo, one line of intent) before the paper
 * begins. Text on it uses `coverInk` / `coverInkSoft`; small orange text is
 * banned here (3.03:1), orange arrives only as washi or a stamp button.
 */
export function CoverBand({ children, bleed = 0, onBack, style }: CoverBandProps) {
  const { colors, space } = useRudiTheme();
  const router = useRouter();
  const back = onBack === true ? () => router.back() : onBack || null;
  return (
    <View
      style={[
        styles.band,
        {
          backgroundColor: colors.cover,
          marginHorizontal: -bleed,
          paddingHorizontal: bleed + space.md,
          paddingTop: space.md,
          paddingBottom: space.lg,
        },
        style,
      ]}
    >
      <Grain material="vaiBia" opacity={0.11} />
      {back ? (
        <PressScale
          accessibilityLabel="Quay lại"
          accessibilityRole="button"
          haptic="select"
          onPress={back}
          pressedScale={0.92}
          style={[styles.back, { backgroundColor: phuMau(colors.coverInk, 0.08) }]}
        >
          <Ionicons color={colors.coverInk} name="chevron-back" size={26} />
        </PressScale>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  band: { borderBottomLeftRadius: 28, borderBottomRightRadius: 28, overflow: "hidden" },
  back: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", marginLeft: -8, marginBottom: 4 },
});
