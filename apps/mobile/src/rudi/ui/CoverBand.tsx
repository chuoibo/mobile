import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import type { ReactNode } from "react";
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { useRudiTheme } from "../theme";

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
      {back ? (
        <Pressable accessibilityLabel="Quay lại" accessibilityRole="button" hitSlop={8} onPress={back} style={styles.back}>
          <Ionicons color={colors.coverInk} name="chevron-back" size={26} />
        </Pressable>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  band: { borderBottomLeftRadius: 28, borderBottomRightRadius: 28, overflow: "hidden" },
  back: { width: 48, height: 48, alignItems: "flex-start", justifyContent: "center", marginLeft: -6, marginTop: -6 },
});
