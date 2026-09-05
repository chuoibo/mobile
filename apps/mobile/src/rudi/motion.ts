/**
 * Motion tokens for the RuDi shell, read from `packages/shared/tokens.json`.
 *
 * The previous `motion` block (press/fade/settle) was declared and never read:
 * every animation in the shell was a `pressed` opacity or a navigator default,
 * and the direction contract promised "motion <= 220ms" against numbers no
 * code consulted. This module is the single place durations and easings are
 * named, so a screen never types `220` on its own.
 *
 * Four steps, four jobs:
 *   instant   press and chip feedback, paired with a haptic
 *   standard  state and content transitions, accordions, skeleton -> content
 *   shared    card -> detail, plan -> timeline, photo -> viewer
 *   celebrate one-shot moments only (outing locked, bill done, badge opened)
 *
 * Two rules the tests pin: Reduce Motion collapses every step but `instant`
 * to zero, and a money count-up may only start once the domain state is
 * valid -- animation never stands in for data on a money screen.
 *
 * Pure: no React, no Reanimated. `ui/useMotion.ts` maps these to Reanimated on
 * the UI thread and reads the system Reduce Motion setting.
 */
import tokens from "../../../../packages/shared/tokens.json";

export type MotionStep = "instant" | "standard" | "shared" | "celebrate";
export type EasingName = "standard" | "decelerate" | "accelerate";
/** cubic-bezier(x1, y1, x2, y2) */
export type Bezier = readonly [number, number, number, number];

const spec = tokens.motion;

export const MOTION_MS: Readonly<Record<MotionStep, number>> = Object.freeze({
  instant: spec.instant,
  standard: spec.standard,
  shared: spec.shared,
  celebrate: spec.celebrate,
});

export const EASING: Readonly<Record<EasingName, Bezier>> = Object.freeze({
  standard: spec.easing.standard as unknown as Bezier,
  decelerate: spec.easing.decelerate as unknown as Bezier,
  accelerate: spec.easing.accelerate as unknown as Bezier,
});

/** The duration to actually run, honouring Reduce Motion. */
export function durationFor(step: MotionStep, reduceMotion: boolean): number {
  if (reduceMotion && step !== "instant") return 0;
  return MOTION_MS[step];
}

/**
 * How long a money figure may count up: `standard` once the domain state is
 * valid, otherwise nothing. A number that animates before the server has
 * confirmed it is a number the screen invented for a few hundred milliseconds.
 */
export function moneyCountUpMs(domainStateValid: boolean, reduceMotion: boolean): number {
  if (!domainStateValid) return 0;
  return durationFor("standard", reduceMotion);
}

/**
 * `celebrate` is a budget of one per event, not a style. The first call for a
 * key wins; every later call for the same key is an ordinary `standard`
 * transition. Callers keep the `seen` set for the lifetime of the screen.
 */
export function celebrateOnce(seen: Set<string>, eventKey: string, reduceMotion: boolean): number {
  if (seen.has(eventKey)) return durationFor("standard", reduceMotion);
  seen.add(eventKey);
  return durationFor("celebrate", reduceMotion);
}
