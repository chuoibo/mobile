import type { ReactNode } from "react";
import { Pressable, type PressableProps, type StyleProp, type ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";

import { useMotion } from "./useMotion";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export interface PressScaleProps extends Omit<PressableProps, "style" | "children"> {
  style?: StyleProp<ViewStyle>;
  /** Scale at full press. 0.97 for cards and rows, 0.94 for a FAB. */
  pressedScale?: number;
  /** Haptic on press: `select` for chips and toggles, `impact` for a primary action. */
  haptic?: "none" | "select" | "impact";
  children?: ReactNode;
}

/**
 * Press feedback on the UI thread: a spring to `pressedScale` on touch-down,
 * a spring back on release, an 8% dim while held. Replaces the `pressed`
 * opacity branches the shell used everywhere, which ran on the JS thread and
 * could not honour Reduce Motion. Under Reduce Motion the spring resolves
 * instantly; the pressed state still shows, it just does not travel.
 */
export function PressScale({
  style,
  pressedScale = 0.97,
  haptic = "none",
  onPressIn,
  onPressOut,
  onPress,
  ...rest
}: PressScaleProps) {
  const motion = useMotion();
  const pressed = useSharedValue(0);
  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: 1 - pressed.value * (1 - pressedScale) }],
    opacity: 1 - pressed.value * 0.08,
  }));

  return (
    <AnimatedPressable
      {...rest}
      style={[style, animatedStyle]}
      onPressIn={(e) => {
        pressed.value = withSpring(1, motion.spring.press);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        pressed.value = withSpring(0, motion.spring.settle);
        onPressOut?.(e);
      }}
      onPress={(e) => {
        if (haptic === "select") motion.haptic.select();
        else if (haptic === "impact") motion.haptic.impact();
        onPress?.(e);
      }}
    />
  );
}
