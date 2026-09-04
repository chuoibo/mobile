/**
 * The QA knob for the keyboard measurement (V3).
 *
 * `scripts/do_ban_phim.py` proves the composer sits above the IME. A proof that
 * cannot fail is not a proof, so the harness has a negative control: with
 * `EXPO_PUBLIC_QA_TAT_KAV=1` the KeyboardAvoidingView is disabled and the same
 * measurement must go red. Plain `process.env.X` member read so Expo inlines it
 * (`tests/env-inlining.test.mjs`); `tests/cau-hinh-ban-dung.test.mjs` refuses it
 * in any shippable eas.json profile.
 */
declare const process: { env: Record<string, string | undefined> };

export const TAT_KAV_QA: boolean = process.env.EXPO_PUBLIC_QA_TAT_KAV === "1";
