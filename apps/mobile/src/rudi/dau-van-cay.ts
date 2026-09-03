/**
 * The tree fingerprint the native gate reads back from the screen.
 *
 * `scripts/mobile_native.sh` proves two things from Metro's log -- that Metro
 * serves THIS tree and that the device bundled from it -- and neither says what
 * the screen is showing. A dev launcher home, or a bundle another lane's Metro
 * served a minute earlier, leaves both anchors green. So the harness inlines a
 * per-run value here and a Maestro flow asserts it is visible; a run that
 * cannot find it is measuring some other screen.
 *
 * Plain `process.env.X` member read on purpose: Expo's inliner ignores
 * optional chaining (see `tests/env-inlining.test.mjs`). Undefined outside the
 * harness, and the two places that render it render nothing then.
 */
declare const process: { env: Record<string, string | undefined> };

export const DAU_VAN_CAY: string | null = process.env.EXPO_PUBLIC_TREE_FINGERPRINT ?? null;
