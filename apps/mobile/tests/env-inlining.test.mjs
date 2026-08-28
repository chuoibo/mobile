/* The one env var a phone needs, and the syntax that silently threw it away.
 *
 * Run from apps/mobile:
 *     node --test tests/env-inlining.test.mjs
 *
 * `EXPO_PUBLIC_API_URL` is how a phone is told where the laptop's API lives.
 * The brief says the phone is the primary target, and a phone can never reach
 * `localhost`, so getting this wrong does not degrade the demo, it ends it.
 *
 * The bug this pins: `src/api.ts` read the variable through optional chaining,
 * `process?.env?.EXPO_PUBLIC_API_URL`. Expo's inliner
 * (babel-preset-expo/build/plugins/inline-env-vars.js) visits both
 * MemberExpression and OptionalMemberExpression, so the outer `?.` was fine --
 * but its `isProcessEnv` guard requires the *object* to be a MemberExpression,
 * and in `process?.env?.X` the object `process?.env` is an
 * OptionalMemberExpression. The guard returned false, no substitution
 * happened, and the built bundle shipped the unresolved expression next to its
 * `?? "http://localhost:8099"` default. Two exports with different values of
 * the variable produced byte-identical bundles, down to the content hash.
 *
 * Why this test transforms rather than exports: `expo export` takes minutes
 * and would put a whole bundler between the defect and the assertion. The
 * substitution is a Babel transform, so this drives that transform directly
 * with the real preset, at the same production caller settings `expo export`
 * uses. The full export is what confirms it end to end and is recorded in the
 * PR; this is what keeps it from coming back.
 *
 * The test is deliberately written against behaviour, not spelling. It does
 * not assert that `src/api.ts` contains a particular string -- it asserts that
 * whatever the file says, a build carries the operator's chosen address. Any
 * rewrite that keeps that property passes.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const babel = require("@babel/core");

// Not hoisted to apps/mobile/node_modules -- expo keeps its own copy. Resolve
// it through expo rather than hardcoding a path into node_modules.
const presetExpo = require.resolve("expo/node_modules/babel-preset-expo");

const API_SOURCE = fileURLToPath(new URL("../src/api.ts", import.meta.url));

/** Build `src/api.ts` the way `expo export --platform web` builds it. */
function buildApiModule(apiUrl) {
  const previous = process.env.EXPO_PUBLIC_API_URL;
  // The inliner reads process.env at transform time, which is exactly how the
  // CLI passes the operator's value down.
  if (apiUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
  else process.env.EXPO_PUBLIC_API_URL = apiUrl;
  try {
    return babel.transformFileSync(API_SOURCE, {
      babelrc: false,
      configFile: false,
      filename: API_SOURCE,
      presets: [[presetExpo, { jsxRuntime: "automatic" }]],
      caller: { name: "metro", platform: "web", isDev: false, supportsStaticESM: true },
    }).code;
  } finally {
    if (previous === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = previous;
  }
}

test("a production build carries the address the operator set", () => {
  const built = buildApiModule("http://laptop.test:8777");
  assert.match(
    built,
    /laptop\.test:8777/,
    "EXPO_PUBLIC_API_URL never reached the bundle, so a phone cannot be pointed at anything",
  );
});

test("setting the address changes the build", () => {
  const one = buildApiModule("http://10.0.0.1:8777");
  const two = buildApiModule("http://10.0.0.2:9111");
  assert.notEqual(
    one,
    two,
    "two different addresses produced identical output, which is how this shipped unnoticed",
  );
});

test("nothing is left for the browser to look up at runtime", () => {
  const built = buildApiModule("http://laptop.test:8777");
  // After inlining there is no lookup left at all: not `process.env.X`, not
  // `process?.env?.X`. A surviving read means the substitution missed, and it
  // will resolve to undefined in a browser and fall through to the default.
  assert.doesNotMatch(
    built,
    /process\s*\??\.\s*\[?["']?env/,
    "a live process.env read survived the transform; the inliner did not match this syntax",
  );
});

test("with nothing set, the local default still applies", () => {
  const built = buildApiModule(undefined);
  assert.match(
    built,
    /localhost:8099/,
    "the developer default disappeared; running with no env var must still work",
  );
});
