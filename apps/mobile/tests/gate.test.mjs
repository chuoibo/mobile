/* What `npm test` actually runs.
 *
 * This file exists because the gate ran nothing at all and said so in a way
 * nobody read. `package.json` invoked `node --test tests/`, and a directory is
 * not a file the runner will load: every run ended with
 *
 *     Error: Cannot find module '.../apps/mobile/tests'
 *     # tests 1  # pass 0  # fail 1
 *
 * -- one failing "test" named `tests`, zero real tests executed, exit 1. Both
 * `test` and `test:e2e` were shaped that way, so the end-to-end run cited as
 * proof that the app talks to the real API had never executed either. A broken
 * runner invocation is worse than a failing test: a failing test names what is
 * wrong, while this one names a module path and looks like a local glitch.
 *
 * So the invocation is now itself under test. Two things are asserted, and the
 * second is the one that matters:
 *
 *   1. Every pattern either gate passes to `node --test` resolves to at least
 *      one real test file -- which is exactly what `tests/` failed.
 *   2. The union of *both* gates covers every `*.test.mjs` under `tests/`.
 *      Adding a test file that no gate reaches is the silent version of the
 *      same failure: the suite stays green while a file nobody runs rots.
 *
 * Why the union of both rather than `npm test` alone. `tests/e2e/` needs a
 * live server and a database only it can seed, so folding it into `npm test`
 * makes the everyday gate depend on whether something happens to be listening
 * on the API port. That was measured, not guessed: four consecutive runs of
 * identical code over a port another worktree was cycling gave 2 failures,
 * then 1, then 1, then 0. A gate whose answer changes without the code
 * changing is worse than one that skips honestly. So `npm test` stays
 * hermetic, `npm run test:e2e` owns the slice, `MOBILE_REQUIRE_E2E=1` is how
 * anyone claiming the app runs against a real API proves it -- and this test
 * keeps the split from turning into a hole, because a file reached by neither
 * gate still fails here.
 *
 * Deliberately not asserted: that the patterns are any particular string. The
 * requirement is that the gates reach the files, not that they spell them a
 * blessed way.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const manifest = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));

/** Every `*.test.mjs` under `tests/`, as paths relative to the package root. */
function everyTestFile(dir = join(ROOT, "tests")) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...everyTestFile(full));
    else if (entry.name.endsWith(".test.mjs")) found.push(relative(ROOT, full));
  }
  return found.sort();
}

/**
 * The arguments the gate hands to `node --test`.
 *
 * Read out of the script string rather than hardcoded, because a copy of the
 * patterns here would pass while the real script pointed somewhere else -- the
 * failure mode this whole file is about.
 */
function runnerPatterns(script) {
  const marker = "node --test ";
  const at = script.lastIndexOf(marker);
  assert.notEqual(at, -1, `khong tim thay "node --test" trong: ${script}`);
  return script
    .slice(at + marker.length)
    .split("&&")[0]
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

/**
 * Expand one shell glob against the tree.
 *
 * `sh` is what actually expands these, so this mirrors it rather than calling
 * out to a matcher with different rules: `*` matches within one path segment
 * and never crosses a `/`. Written out because `fs.globSync` landed in Node 22
 * and CI still runs Node 20 -- a helper that only works on the newer runtime
 * would make this test pass locally and vanish where it is needed.
 */
function expand(pattern) {
  let level = [""];
  for (const segment of pattern.split("/")) {
    const next = [];
    for (const base of level) {
      const here = join(ROOT, base);
      if (!segment.includes("*")) {
        try {
          statSync(join(here, segment));
          next.push(base ? `${base}/${segment}` : segment);
        } catch {
          /* a literal segment that is not there expands to nothing, as in sh */
        }
        continue;
      }
      const rule = new RegExp(
        `^${segment.split("*").map((s) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join("[^/]*")}$`,
      );
      let entries;
      try {
        entries = readdirSync(here);
      } catch {
        continue;
      }
      for (const name of entries.sort()) {
        if (rule.test(name)) next.push(base ? `${base}/${name}` : name);
      }
    }
    level = next;
  }
  return level;
}

/** The two scripts that invoke `node --test`, by name. */
const GATES = ["test", "test:e2e"];

test("mỗi mẫu trong hai lệnh test đều trỏ tới file có thật", () => {
  for (const gate of GATES) {
    for (const pattern of runnerPatterns(manifest.scripts[gate])) {
      const matched = expand(pattern);
      assert.ok(
        matched.length > 0,
        `"${pattern}" trong "${gate}" khong khop file nao — node --test se bao MODULE_NOT_FOUND`,
      );
      for (const hit of matched) {
        assert.ok(
          statSync(join(ROOT, hit)).isFile(),
          `"${pattern}" khop thu muc ${hit}, khong phai file test`,
        );
        assert.ok(hit.endsWith(".test.mjs"), `${hit} khong phai file test`);
      }
    }
  }
});

test("mọi file test đều có ít nhất một cổng chạy tới", () => {
  const reached = new Set(
    GATES.flatMap((gate) =>
      runnerPatterns(manifest.scripts[gate]).flatMap((pattern) => expand(pattern)),
    ),
  );
  const missed = everyTestFile().filter((file) => !reached.has(file));
  assert.deepEqual(missed, [], `co file test khong cong nao chay toi: ${missed}`);
});

test("test:e2e chạy đúng bài end-to-end", () => {
  // The narrower gate has to reach the slice, or `npm run test:e2e` becomes a
  // command that reports success without going near the API.
  const reached = new Set(
    runnerPatterns(manifest.scripts["test:e2e"]).flatMap((pattern) => expand(pattern)),
  );
  assert.ok(
    reached.has("tests/e2e/vertical-slice.test.mjs"),
    `test:e2e khong cham toi bai end-to-end, chi thay: ${[...reached]}`,
  );
});

test("npm test dựng app trước khi chạy test", () => {
  // Ordering, not presence. A suite that runs before the bundle is built can
  // be green while the app cannot start -- which happened: a screen imported a
  // file Metro would not resolve, and the test tsconfig compiles three logic
  // modules and no screens, so nothing noticed.
  const script = manifest.scripts.test;
  const built = script.indexOf("build:check");
  const ran = script.lastIndexOf("node --test");
  assert.notEqual(built, -1, "npm test khong dung app truoc");
  assert.ok(built < ran, "test chay truoc khi dung app");
});
