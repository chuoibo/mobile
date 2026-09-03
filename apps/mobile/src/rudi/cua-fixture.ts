/**
 * Whether the "Vào bản trải nghiệm" door exists on this build.
 *
 * The fixture story (Team Đà Lạt) is a QA surface, not a product: the Maestro
 * table drives it, the design system is measured on it, and nobody signed in
 * should ever land on it. So the door is behind two switches that a shipped
 * build cannot have at once -- a development build (`__DEV__`) AND an operator
 * saying so at bundle time. `scripts/mobile_native.sh` sets the variable; a
 * store build has neither and the door is not rendered, not merely disabled.
 *
 * Plain `process.env.X` member read on purpose (`tests/env-inlining.test.mjs`).
 * `__DEV__` is a Metro/RN global; under node tests it may not exist, hence the
 * typeof guard rather than a bare read that would throw at import.
 */
declare const process: { env: Record<string, string | undefined> };
declare const __DEV__: boolean | undefined;

const BAT_FIXTURE = process.env.EXPO_PUBLIC_RUDI_FIXTURE;

export const CUA_FIXTURE_DEV: boolean =
  (typeof __DEV__ === "boolean" ? __DEV__ : false) && BAT_FIXTURE === "1";
