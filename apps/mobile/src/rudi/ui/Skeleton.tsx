import { LinearGradient } from "expo-linear-gradient";
import { useEffect } from "react";
import { StyleSheet, View, type DimensionValue, type StyleProp, type ViewStyle } from "react-native";
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { phuMau, useRudiTheme } from "../theme";
import { useMotion } from "./useMotion";

/**
 * Loading is a shape, not a sentence.
 *
 * Until now every live screen said «Đang đọc … từ máy chủ...» in a grey
 * caption and then swapped in a layout of a different height. The direction
 * round's second raise (from the woodblock challenger) is the rule here: the
 * frame prints first, the ink arrives when the data does, and the frame never
 * moves. So a skeleton is drawn in the exact shape of the content it stands
 * for: a row for a row, a card for a card, lines at the real line height.
 *
 * The shimmer is a `translateX` band on the UI thread; it is not ambient
 * decoration because it ends the moment content lands, and under Reduce
 * Motion it does not run at all -- the bone is simply still.
 */

const SHIMMER_MS = 1400;

interface BoneProps {
  width?: DimensionValue;
  height: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}

/** One bone. Compose the shapes below from it; screens rarely need it alone. */
export function Skeleton({ width = "100%", height, radius, style }: BoneProps) {
  const { colors, radius: r } = useRudiTheme();
  const motion = useMotion();
  const phase = useSharedValue(0);

  useEffect(() => {
    if (motion.reduced) {
      phase.value = 0;
      return;
    }
    phase.value = withRepeat(
      withTiming(1, { duration: SHIMMER_MS, easing: Easing.inOut(Easing.ease) }),
      -1,
      false,
    );
    return () => cancelAnimation(phase);
  }, [motion.reduced, phase]);

  const band = useAnimatedStyle(() => ({
    transform: [{ translateX: -160 + phase.value * 480 }],
  }));

  return (
    <View
      style={[
        { width, height, borderRadius: radius ?? r.small, backgroundColor: colors.line, overflow: "hidden" },
        style,
      ]}
    >
      {motion.reduced ? null : (
        <Animated.View style={[StyleSheet.absoluteFill, band]}>
          <LinearGradient
            colors={[phuMau(colors.card, 0), phuMau(colors.card, 0.55), phuMau(colors.card, 0)]}
            start={{ x: 0, y: 0.5 }}
            end={{ x: 1, y: 0.5 }}
            style={styles.band}
          />
        </Animated.View>
      )}
    </View>
  );
}

interface LinesProps {
  lines?: number;
  lineHeight?: number;
  gap?: number;
  /** Width of the last line, so a paragraph reads as a paragraph. */
  lastWidth?: DimensionValue;
  style?: StyleProp<ViewStyle>;
}

/** A paragraph: full lines and a shorter last one, at the real line height. */
export function SkeletonLines({ lines = 3, lineHeight = 14, gap = 8, lastWidth = "62%", style }: LinesProps) {
  return (
    <View style={[{ gap }, style]}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} height={lineHeight} width={i === lines - 1 && lines > 1 ? lastWidth : "100%"} />
      ))}
    </View>
  );
}

interface RowProps {
  /** Leading avatar or icon tile size; 0 for none. */
  leading?: number;
  lines?: number;
  style?: StyleProp<ViewStyle>;
}

/** The shape of a `ListRow` or a conversation row. */
export function SkeletonRow({ leading = 40, lines = 2, style }: RowProps) {
  const { space } = useRudiTheme();
  return (
    <View style={[styles.row, { gap: space.sm, paddingVertical: space.sm }, style]}>
      {leading > 0 ? <Skeleton width={leading} height={leading} radius={leading / 2} /> : null}
      <SkeletonLines lines={lines} lineHeight={lines === 1 ? 16 : 13} gap={7} lastWidth="45%" style={styles.grow} />
    </View>
  );
}

interface CardProps {
  /** Height of a media slot above the text; 0 for a text-only card. */
  media?: number;
  lines?: number;
  style?: StyleProp<ViewStyle>;
}

/** The shape of a card with an optional media slot. */
export function SkeletonCard({ media = 0, lines = 2, style }: CardProps) {
  const { colors, radius, space } = useRudiTheme();
  return (
    <View
      style={[
        { borderRadius: radius.base, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.line, overflow: "hidden" },
        style,
      ]}
    >
      {media > 0 ? <Skeleton height={media} radius={0} /> : null}
      <View style={{ padding: space.md, gap: space.sm }}>
        <Skeleton height={18} width="70%" />
        <SkeletonLines lines={lines} lineHeight={13} gap={7} lastWidth="50%" />
      </View>
    </View>
  );
}

/**
 * Wraps a screen's skeleton so assistive tech hears one thing, once, instead
 * of a dozen empty views.
 */
export function SkeletonGroup({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <View accessible accessibilityLabel="Đang tải" accessibilityRole="progressbar" style={style}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  band: { width: 160, height: "100%" },
  row: { flexDirection: "row", alignItems: "center" },
  grow: { flex: 1 },
});
