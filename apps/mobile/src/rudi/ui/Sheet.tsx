import { useEffect, type ReactNode } from "react";
import { BackHandler, Platform, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { lopPhu, useRudiTheme } from "../theme";
import { useMotion } from "./useMotion";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Announced to assistive tech when the sheet opens. */
  accessibilityLabel: string;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * A bottom sheet on the UI thread: scrim fades over `standard`, the panel
 * springs up and settles, Back and the scrim both close it. It is not a modal
 * route, so it can live inside a screen (create menu, picker, filters) and be
 * driven by state; `app/create.tsx` still hand-rolls one and moves here in
 * UI-7. Under Reduce Motion the spring resolves instantly.
 */
export function Sheet({ open, onClose, children, accessibilityLabel, style, testID }: SheetProps) {
  const { colors, radius, space } = useRudiTheme();
  const insets = useSafeAreaInsets();
  const motion = useMotion();
  const progress = useSharedValue(open ? 1 : 0);

  useEffect(() => {
    progress.value = open ? withSpring(1, motion.spring.settle) : withTiming(0, motion.timing("standard"));
  }, [open, motion, progress]);

  useEffect(() => {
    if (!open || Platform.OS !== "android") return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [open, onClose]);

  const scrim = useAnimatedStyle(() => ({ opacity: progress.value }));
  const panel = useAnimatedStyle(() => ({
    transform: [{ translateY: (1 - progress.value) * 480 }],
  }));

  if (!open && progress.value === 0) return null;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents={open ? "auto" : "none"} testID={testID}>
      <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: lopPhu.toi(0.42) }, scrim]}>
        <Pressable accessibilityLabel="Đóng" accessibilityRole="button" onPress={onClose} style={StyleSheet.absoluteFill} />
      </Animated.View>
      <Animated.View
        accessibilityViewIsModal
        accessibilityLabel={accessibilityLabel}
        style={[
          styles.panel,
          {
            backgroundColor: colors.card,
            borderTopLeftRadius: radius.base,
            borderTopRightRadius: radius.base,
            paddingHorizontal: space.md,
            paddingTop: space.sm,
            paddingBottom: Math.max(insets.bottom, space.md),
          },
          panel,
          style,
        ]}
      >
        <View style={[styles.handle, { backgroundColor: colors.lineStrong }]} />
        {children}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { position: "absolute", left: 0, right: 0, bottom: 0 },
  handle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, marginBottom: 12 },
});
