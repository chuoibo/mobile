import * as Haptics from "expo-haptics";
import { useMemo } from "react";
import {
  Easing,
  ReduceMotion,
  useReducedMotion,
  type WithSpringConfig,
  type WithTimingConfig,
} from "react-native-reanimated";

import { EASING, durationFor, type EasingName, type MotionStep } from "../motion";

/**
 * The shell's motion tokens, bound to Reanimated and to the system Reduce
 * Motion setting. Every animated primitive reads this hook; no screen calls
 * `withTiming` with a number of its own.
 */
export interface MotionKit {
  /** The OS asked for less motion; durations other than `instant` are 0. */
  reduced: boolean;
  ms(step: MotionStep): number;
  timing(step: MotionStep, easing?: EasingName): WithTimingConfig;
  spring: { press: WithSpringConfig; settle: WithSpringConfig };
  haptic: { select(): void; impact(): void; success(): void };
}

export function useMotion(): MotionKit {
  const reduced = useReducedMotion();
  return useMemo(() => {
    const ms = (step: MotionStep) => durationFor(step, reduced);
    const bezier = (name: EasingName) => {
      const [x1, y1, x2, y2] = EASING[name];
      return Easing.bezier(x1, y1, x2, y2);
    };
    return {
      reduced,
      ms,
      timing: (step, easing = "standard") => ({
        duration: ms(step),
        easing: bezier(easing),
        reduceMotion: ReduceMotion.System,
      }),
      spring: {
        // Press: quick, slightly overdamped, so a tap never wobbles.
        press: { damping: 18, stiffness: 260, mass: 0.6, reduceMotion: ReduceMotion.System },
        // Settle: a sheet or a card coming to rest.
        settle: { damping: 20, stiffness: 180, mass: 0.8, reduceMotion: ReduceMotion.System },
      },
      haptic: {
        select: () => void Haptics.selectionAsync(),
        impact: () => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium),
        success: () => void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
      },
    };
  }, [reduced]);
}
