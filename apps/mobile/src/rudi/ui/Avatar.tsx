import { Image, type ImageSource } from "expo-image";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { chuDau } from "../../screens/ca-nhan/ban-be";
import { MOTION_MS } from "../motion";
import { typography, useRudiTheme, type RudiTone } from "../theme";

export interface AvatarProps {
  name: string;
  /** Resolved by the screen (`nguonAnh` for group photos, the avatar helper for people); null = initials. */
  source?: ImageSource | null;
  size?: number;
  /** A ring marks the person who is speaking, paying, or being pointed at. */
  ring?: boolean;
  tone?: RudiTone;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * A person, at any size. Photo when the person uploaded one (M8), initials
 * otherwise -- never a stock face, never a photo of a real person that did not
 * come from them. Colour is deliberately *not* per person: in this product a
 * colour names a part of the app (orange = action, teal = money, violet = AI),
 * so an avatar palette keyed to people would give each friend a meaning they
 * do not have. The tint is the screen's tone; identity is the letter or the
 * photo.
 */
export function Avatar({ name, source = null, size = 44, ring = false, tone = "accent", style, testID }: AvatarProps) {
  const { colors } = useRudiTheme();
  const soft = tone === "accent" ? colors.accentSoft : tone === "split" ? colors.splitSoft : colors.aiSoft;
  const ink = colors[tone];
  const frame: ViewStyle = {
    width: size,
    height: size,
    borderRadius: size / 2,
    backgroundColor: soft,
    borderWidth: 2,
    borderColor: ring ? ink : colors.card,
  };
  return (
    <View accessibilityLabel={name} testID={testID} style={[styles.center, frame, style]}>
      {source ? (
        <Image
          source={source}
          contentFit="cover"
          transition={MOTION_MS.standard}
          style={[StyleSheet.absoluteFill, { borderRadius: size / 2 }]}
        />
      ) : (
        <Text style={[typography.label, { color: ink, fontSize: Math.max(11, Math.round(size * 0.38)), lineHeight: undefined }]}>
          {chuDau(name)}
        </Text>
      )}
    </View>
  );
}

export interface AvatarStackProps {
  people: { name: string; source?: ImageSource | null }[];
  size?: number;
  max?: number;
  tone?: RudiTone;
  style?: StyleProp<ViewStyle>;
}

/** Overlapping heads with a «+N» tail; the count is the honest number, not a mood. */
export function AvatarStack({ people, size = 32, max = 4, tone = "accent", style }: AvatarStackProps) {
  const { colors } = useRudiTheme();
  const shown = people.slice(0, max);
  const rest = people.length - shown.length;
  return (
    <View accessibilityLabel={`${people.length} người`} style={[styles.row, style]}>
      {shown.map((p, i) => (
        <Avatar key={`${p.name}-${i}`} name={p.name} source={p.source} size={size} tone={tone} style={i > 0 ? { marginLeft: -size * 0.3 } : undefined} />
      ))}
      {rest > 0 ? (
        <View
          style={[
            styles.center,
            { width: size, height: size, borderRadius: size / 2, marginLeft: -size * 0.3, backgroundColor: colors.card, borderWidth: 2, borderColor: colors.line },
          ]}
        >
          <Text style={[typography.caption, { color: colors.inkSoft }]}>+{rest}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center" },
});
