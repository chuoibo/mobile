import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { typography, useRudiTheme, type RudiTone } from "../theme";

export interface StepperProps {
  steps: string[];
  /** Zero-based index of the current step. */
  current: number;
  tone?: RudiTone;
  /** Why the primary action is locked right now, in one sentence; nothing when it is not. */
  lockedReason?: string | null;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * Where am I, and why can I not go on yet.
 *
 * The bill flow and outing creation are multi-step, and the audit's heuristic
 * scores (system status 2/4, help 1/4) came largely from CTAs that were
 * disabled with no sentence saying why. The stepper answers both in one
 * strip: a filled segment per completed step, the current step named, and the
 * lock reason printed right under it instead of hidden in a greyed button.
 */
export function Stepper({ steps, current, tone = "accent", lockedReason = null, style, testID }: StepperProps) {
  const { colors, space } = useRudiTheme();
  const ink = colors[tone];
  const clamped = Math.min(Math.max(current, 0), Math.max(steps.length - 1, 0));
  return (
    <View
      testID={testID}
      accessibilityRole="progressbar"
      accessibilityLabel={`Bước ${clamped + 1} trên ${steps.length}: ${steps[clamped] ?? ""}`}
      style={[{ gap: space.xs }, style]}
    >
      <View style={[styles.track, { gap: space.xs }]}>
        {steps.map((label, i) => (
          <View
            key={label}
            style={[
              styles.segment,
              { backgroundColor: i <= clamped ? ink : colors.line, opacity: i < clamped ? 0.55 : 1 },
            ]}
          />
        ))}
      </View>
      <View style={styles.row}>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          Bước {clamped + 1}/{steps.length}
        </Text>
        <Text numberOfLines={1} style={[typography.label, { color: colors.ink, flex: 1, textAlign: "right" }]}>
          {steps[clamped]}
        </Text>
      </View>
      {lockedReason ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>{lockedReason}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  track: { flexDirection: "row" },
  segment: { flex: 1, height: 4, borderRadius: 2 },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
});
