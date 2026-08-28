/* Whether the app can be pointed at a server that is not this laptop.
 *
 * `api.ts` says the address is "overridable so a phone can reach a laptop".
 * It was not. Expo inlines `EXPO_PUBLIC_*` by substituting the exact member
 * expression `process.env.EXPO_PUBLIC_API_URL` at build time; the source wrote
 * `process?.env?.EXPO_PUBLIC_API_URL`, and optional chaining is a different
 * AST node, so nothing was ever substituted. The emitted bundle read
 *
 *     ("undefined"!=typeof process?process?.env?.EXPO_PUBLIC_API_URL:void 0)
 *       ?? "http://localhost:8099"
 *
 * and at runtime there is no `process.env` on a device, so every build fell
 * back to `http://localhost:8099` no matter what the environment said. On a
 * phone that address is the phone, so the app could never reach anything. The
 * one documented way to run against a real server did nothing, silently, and
 * the docstring promising it made it look handled.
 *
 * This is checked against the built bundle rather than the source, because the
 * thing that broke was a build-time transform. A source-level assertion would
 * have passed on the code that shipped broken -- `EXPO_PUBLIC_API_URL` is
 * right there in the text either way. Only the artifact knows.
 *
 * `npm test` builds with SENTINEL set, so this costs no extra build.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/** Must match `build:check` in package.json. */
const SENTINEL = "http://api.build-check.invalid";

function builtBundle() {
  const dir = join(ROOT, ".expo-build-check/_expo/static/js/web");
  let names;
  try {
    names = readdirSync(dir).filter((name) => name.endsWith(".js"));
  } catch {
    assert.fail(
      "khong tim thay ban dung web. Chay `npm run build:check` truoc, " +
        "hoac chay `npm test` (no tu dung truoc khi test).",
    );
  }
  assert.equal(names.length, 1, `mong doi dung 1 bundle, thay: ${names}`);
  return readFileSync(join(dir, names[0]), "utf8");
}

test("EXPO_PUBLIC_API_URL thật sự đi được vào bản dựng", () => {
  const bundle = builtBundle();
  assert.ok(
    bundle.includes(SENTINEL),
    `dat EXPO_PUBLIC_API_URL=${SENTINEL} luc dung nhung ban dung khong he co no. ` +
      "Expo chi thay the dung chuoi `process.env.EXPO_PUBLIC_API_URL`; " +
      "viet `process?.env?.` thi khong duoc thay the va app luon goi localhost.",
  );
});

test("không còn phép đọc biến môi trường nào sót lại lúc chạy", () => {
  // The discriminator, and the reason it is this and not "localhost is
  // absent": the fallback literal is supposed to survive -- a developer with
  // no override should still reach their own laptop. What must NOT survive is
  // an unsubstituted read. Expo replaces the whole expression with a string,
  // so a build that worked has no `EXPO_PUBLIC_API_URL` left anywhere; the
  // build that shipped broken still carried the name, waiting to read a
  // `process.env` that does not exist on a device.
  const bundle = builtBundle();
  assert.ok(
    !bundle.includes("EXPO_PUBLIC_API_URL"),
    "ban dung van con doc EXPO_PUBLIC_API_URL luc chay — Expo chua thay the, " +
      "nghia la tren may that no se roi ve localhost",
  );
});
