import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { typography, useRudiTheme, type RudiTone } from "../theme";

export interface StampProps {
  /** Short, factual: «ĐÃ TỚI», «ĐÃ TRẢ», «ĐANG MỞ», «AI GỢI Ý». */
  label: string;
  tone?: RudiTone;
  /** `ink` for a filled seal (rare: the one state that matters most on the screen). */
  variant?: "outline" | "ink";
  /** A slight rotation makes a seal read as pressed, not printed; 0 for tables. */
  tilt?: -3 | -2 | 0 | 2 | 3;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * A rubber stamp for a state that is true.
 *
 * DESIGN.md already ruled that a status is a static chip, not inline text.
 * In the journal world that chip is an ink seal: a 2dp border in the tone,
 * condensed caps from the display face, a hair of rotation. It carries a
 * meaning colour (teal = money, orange = the ask, violet = AI) *and* a word,
 * so state never rides on colour alone. Not a control: no role, no press.
 */
export function Stamp({ label, tone = "accent", variant = "outline", tilt = 0, style, testID }: StampProps) {
  const { colors } = useRudiTheme();
  const ink = colors[tone];
  const filled = variant === "ink";
  const onInk = tone === "accent" ? colors.accentInk : tone === "split" ? colors.splitInk : colors.aiInk;
  return (
    <View
      testID={testID}
      accessibilityLabel={label}
      style={[
        styles.seal,
        {
          borderColor: ink,
          backgroundColor: filled ? ink : "transparent",
          ...(tilt === 0 ? {} : { transform: [{ rotate: `${tilt}deg` }] }),
        },
        style,
      ]}
    >
      <Text style={[typography.stamp, { color: filled ? onInk : ink }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  seal: {
    alignSelf: "flex-start",
    borderWidth: 2,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minHeight: 26,
    justifyContent: "center",
  },
});
