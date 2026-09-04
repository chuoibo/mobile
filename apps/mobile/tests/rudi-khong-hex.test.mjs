/* Colour literals in the RuDi shell may only disappear, never appear.
 *
 * Run from apps/mobile:
 *     node --test tests/rudi-khong-hex.test.mjs
 *
 * `packages/shared/tokens.json` is the one colour source (DESIGN.md, and
 * `services/api/tests/web/test_shared_tokens.py` holds the guest page to it token
 * by token). The shell under `src/rudi/` and `app/` grew 150+ `#hex` / `rgba()`
 * literals beside those tokens -- per-person colours, receipt paper, chip tints,
 * a star -- and every one of them is a colour the design system cannot see,
 * cannot re-measure for contrast, and cannot switch for dark mode.
 *
 * This is a debt list, not a licence: each file below is pinned at the count it
 * had when the list was written. A file may drop below its pin (then the pin
 * must be lowered, so the list cannot quietly outlive the debt it names) and no
 * file may rise above it or join the list. `src/rudi/theme.ts` is the only file
 * allowed to spell colours, because that is where tokens become RN styles.
 *
 * Counting is by regex on source text, deliberately: the question is "does a
 * colour literal exist in this file", not "is it used", and a parser would only
 * add ways for a literal to hide (template strings, computed keys).
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const LITERAL = /#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g;
const ONLY_FILE_ALLOWED_TO_SPELL_COLOURS = "src/rudi/theme.ts";

// Pinned 2026-09-03 on the dev-client harness branch. Lower a number when you
// remove literals; never raise one. Removing a file's last literal means
// deleting its line here, and the test tells you so.
const NO_DA_BIET = {
  "src/rudi/screens/Bill.tsx": 28,
  "src/rudi/screens/Profile.tsx": 27,
  "src/rudi/fixtures.ts": 20,
  "src/rudi/screens/Discovery.tsx": 19,
  "src/rudi/screens/Onboarding.tsx": 18,
  "src/rudi/screens/Memories.tsx": 14,
  "src/rudi/screens/Outing.tsx": 13,
  "src/rudi/ui.tsx": 7,
  "src/rudi/screens/Create.tsx": 4,
  "src/rudi/session.tsx": 2,
  "src/rudi/screens/Group.tsx": 1,
  "src/rudi/nguon.ts": 1,
  "src/rudi/kho.ts": 1,
};

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(tsx?|jsx?)$/.test(name)) yield full;
  }
}

function count() {
  const found = {};
  for (const dir of ["src/rudi", "app"]) {
    for (const file of walk(join(ROOT, dir))) {
      const rel = relative(ROOT, file).split("\\").join("/");
      if (rel === ONLY_FILE_ALLOWED_TO_SPELL_COLOURS) continue;
      const n = (readFileSync(file, "utf8").match(LITERAL) ?? []).length;
      if (n > 0) found[rel] = n;
    }
  }
  return found;
}

test("no file in the shell gained a colour literal, and no new file joined the list", () => {
  const found = count();
  const worse = Object.entries(found)
    .filter(([file, n]) => n > (NO_DA_BIET[file] ?? 0))
    .map(([file, n]) => `${file}: ${n} > ${NO_DA_BIET[file] ?? 0} (dùng token ở packages/shared/tokens.json qua src/rudi/theme.ts)`);
  assert.deepEqual(worse, [], `màu viết tay mới:\n  ${worse.join("\n  ")}`);
});

test("every pin still describes real debt, so the list cannot outlive it", () => {
  const found = count();
  const stale = Object.entries(NO_DA_BIET)
    .filter(([file, pinned]) => (found[file] ?? 0) < pinned)
    .map(([file, pinned]) => `${file}: ghim ${pinned}, còn ${found[file] ?? 0} — hạ số (hoặc xoá dòng) trong NO_DA_BIET`);
  assert.deepEqual(stale, [], `ghim cũ:\n  ${stale.join("\n  ")}`);
});

test("the reader itself is alive: it sees the theme file's literals when not excluded", () => {
  const theme = readFileSync(join(ROOT, ONLY_FILE_ALLOWED_TO_SPELL_COLOURS), "utf8");
  const n = (theme.match(LITERAL) ?? []).length;
  assert.ok(n >= 0, "theme.ts readable");
  // A deliberately bad sample must be counted, or a zero elsewhere means nothing.
  assert.equal(("color: '#ABCDEF'; background: rgba(1,2,3,0.4)".match(LITERAL) ?? []).length, 2);
});
