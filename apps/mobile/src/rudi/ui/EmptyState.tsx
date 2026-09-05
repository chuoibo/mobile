import type { ReactNode } from "react";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { typography, useRudiTheme, type RudiTone } from "../theme";
import { RudiButton } from "../ui";

/**
 * Five different silences, never one «nothing here».
 *
 * `first-use`   the person has never done this yet; teach the first step
 * `no-results`  a search or AI query found nothing; offer a wider net
 * `filtered`    a filter hides everything; offer to clear it
 * `permission`  the OS said no; explain what the permission buys and how to grant
 * `failure`     the server or network failed; retry, and keep what was typed
 *
 * The audit counted twelve hand-rolled empty states in the shell, each a Card
 * with an icon circle and a centred h2. This is the one shape they collapse
 * into; the illustration slot is where the visual world speaks (an SVG per
 * category, a stamp, a torn ticket) and stays empty until it does.
 */
export type EmptyKind = "first-use" | "no-results" | "filtered" | "permission" | "failure";

export interface EmptyStateProps {
  kind: EmptyKind;
  title: string;
  /** One sentence naming the next step, in the product's own words. */
  body?: string;
  /** The one action that resolves this silence. */
  action?: { label: string; onPress: () => void; loading?: boolean };
  /** A quieter second door (e.g. «Mời bạn» beside «Tạo nhóm»). */
  secondary?: { label: string; onPress: () => void };
  /** Authored artwork from the visual world; nothing renders when absent. */
  illustration?: ReactNode;
  tone?: RudiTone;
  /** `full` centres in the viewport; `inline` sits inside a list at content width. */
  layout?: "full" | "inline";
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function EmptyState({
  kind,
  title,
  body,
  action,
  secondary,
  illustration,
  tone = "accent",
  layout = "full",
  style,
  testID,
}: EmptyStateProps) {
  const { colors, space } = useRudiTheme();
  const full = layout === "full";
  return (
    <View
      testID={testID ?? `empty-${kind}`}
      accessibilityRole="summary"
      style={[full ? styles.full : styles.inline, { gap: space.sm, paddingVertical: full ? space.xl : space.md }, style]}
    >
      {illustration ? <View style={{ marginBottom: space.xs }}>{illustration}</View> : null}
      <Text style={[typography.h2, { color: colors.ink, textAlign: full ? "center" : "left", maxWidth: 420 }]}>
        {title}
      </Text>
      {body ? (
        <Text style={[typography.body, { color: colors.inkSoft, textAlign: full ? "center" : "left", maxWidth: 420 }]}>
          {body}
        </Text>
      ) : null}
      {action || secondary ? (
        <View style={[styles.actions, { gap: space.sm, marginTop: space.xs, alignSelf: full ? "center" : "flex-start" }]}>
          {action ? (
            <RudiButton
              label={action.label}
              onPress={action.onPress}
              loading={action.loading}
              tone={kind === "failure" ? "accent" : tone}
              variant={kind === "failure" ? "outline" : "solid"}
              compact
            />
          ) : null}
          {secondary ? (
            <RudiButton label={secondary.label} onPress={secondary.onPress} tone={tone} variant="ghost" compact />
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  full: { alignItems: "center", justifyContent: "center", flexGrow: 1 },
  inline: { alignItems: "flex-start" },
  actions: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
});
