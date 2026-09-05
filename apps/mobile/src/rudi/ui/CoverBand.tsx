import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import type { ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { phuMau, useRudiTheme } from "../theme";
import { Grain } from "./Grain";
import { PressScale } from "./PressScale";

export interface CoverBandProps {
  children: ReactNode;
  /** Bleed past the screen's horizontal padding so the cloth reaches the edges. */
  bleed?: number;
  /** Draw a back chevron in cover ink; `true` pops the router, a function runs instead. */
  onBack?: boolean | (() => void);
  /**
   * The band is the first thing on the screen: it paints under the status bar
   * and keeps its own content below it. Pair with `RudiScreen surface="cover"`,
   * which then adds no top inset of its own -- the inset as page padding is
   * exactly the paper strip between status bar and band that the 2026-09-05
   * review flagged.
   */
  underStatusBar?: boolean;
  style?: StyleProp<ViewStyle>;
}

/**
 * The notebook's cover as a band at the top of a page: indigo cloth carrying
 * the brand moment (greeting, logo, one line of intent) before the paper
 * begins. Text on it uses `coverInk` / `coverInkSoft`; small orange text is
 * banned here (3.03:1), orange arrives only as washi or a stamp button.
 */
export function CoverBand({ children, bleed = 0, onBack, underStatusBar = false, style }: CoverBandProps) {
  const { colors, space } = useRudiTheme();
  const insets = useSafeAreaInsets();
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
          paddingTop: space.md + (underStatusBar ? insets.top : 0),
          paddingBottom: space.lg,
        },
        style,
      ]}
    >
      <Grain material="vaiBia" opacity={0.3} />
      {back ? (
        <PressScale
          accessibilityLabel="Quay lại"
          accessibilityRole="button"
          haptic="select"
          onPress={back}
          pressedScale={0.92}
          style={styles.backHit}
        >
          {/* The round face is a child, so the animated pressable itself paints nothing rectangular. */}
          <View style={[styles.back, { backgroundColor: phuMau(colors.coverInk, 0.08) }]}>
            <Ionicons color={colors.coverInk} name="chevron-back" size={26} />
          </View>
        </PressScale>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  band: { borderBottomLeftRadius: 28, borderBottomRightRadius: 28, overflow: "hidden" },
  backHit: { width: 48, height: 48, marginLeft: -8, marginBottom: 4 },
  back: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
});
