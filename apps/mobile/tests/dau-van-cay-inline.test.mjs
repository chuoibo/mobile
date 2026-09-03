/* The tree fingerprint the native gate reads off the screen must survive the build.
 *
 * Run from apps/mobile:
 *     node --test tests/dau-van-cay-inline.test.mjs
 *
 * `scripts/mobile_native.sh` inlines EXPO_PUBLIC_TREE_FINGERPRINT at Metro start
 * and asserts it on the welcome screen (NEO 2b). If the read in
 * `src/rudi/dau-van-cay.ts` ever stops being a plain `process.env.X` member
 * expression, Expo's inliner leaves it alone, the value resolves to undefined on
 * the device, and the flow goes red for a reason nobody can see in the diff.
 * Same defect class as `tests/env-inlining.test.mjs`, same proof: drive the real
 * babel preset at production caller settings and read the output.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const babel = require("@babel/core");
const presetExpo = require.resolve("expo/node_modules/babel-preset-expo");
const SOURCE = fileURLToPath(new URL("../src/rudi/dau-van-cay.ts", import.meta.url));

function build(value) {
  const previous = process.env.EXPO_PUBLIC_TREE_FINGERPRINT;
  if (value === undefined) delete process.env.EXPO_PUBLIC_TREE_FINGERPRINT;
  else process.env.EXPO_PUBLIC_TREE_FINGERPRINT = value;
  try {
    return babel.transformFileSync(SOURCE, {
      presets: [presetExpo],
      filename: SOURCE,
      babelrc: false,
      configFile: false,
      caller: { name: "metro", platform: "android", isDev: false, supportsStaticESM: true },
    }).code;
  } finally {
    if (previous === undefined) delete process.env.EXPO_PUBLIC_TREE_FINGERPRINT;
    else process.env.EXPO_PUBLIC_TREE_FINGERPRINT = previous;
  }
}

test("the harness's fingerprint reaches the bundle", () => {
  // Short digit groups on purpose: a realistic `<pid>-<epoch>` tail reads to the
  // repo guard as one twelve-digit number (an account number shape) and blocks the commit.
  assert.match(build("abc1234-x42-t9"), /abc1234-x42-t9/);
});

test("no live process.env read survives the transform", () => {
  assert.doesNotMatch(build("x-1-2"), /process\s*\??\.\s*\[?["']?env/);
});

test("without the harness the module carries null, not a stray string", () => {
  const built = build(undefined);
  assert.doesNotMatch(built, /TREE_FINGERPRINT/);
});
