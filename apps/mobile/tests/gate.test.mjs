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
import { execFileSync } from "node:child_process";
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
 * The argument text the gate hands to `node --test`, before the shell sees it.
 *
 * Read out of the script string rather than hardcoded, because a copy of the
 * patterns here would pass while the real script pointed somewhere else -- the
 * failure mode this whole file is about.
 */
function runnerArgumentText(script) {
  const marker = "node --test ";
  const at = script.lastIndexOf(marker);
  assert.notEqual(at, -1, `khong tim thay "node --test" trong: ${script}`);
  return script.slice(at + marker.length).split("&&")[0].trim();
}

/**
 * What `node --test` actually receives, expanded by the shell that will expand
 * it for real.
 *
 * An earlier version of this file reimplemented `sh` glob expansion by hand.
 * That was wrong in a way worth recording, because it looked right: a model of
 * the shell only understands the constructs its author thought of. It knew `*`
 * and nothing else, so the moment the gate moved to
 * `$(find tests -name '*.test.mjs')` the model read `$(find` as a filename,
 * matched nothing, and reported a broken gate that was in fact fine. A checker
 * that fails on correct input is not a stricter checker, it is a wrong one, and
 * it would have blocked the very repair it exists to protect.
 *
 * So the shell is asked instead of imitated. `printf` re-emits each expanded
 * word on its own line, which is exactly the argument vector `node --test`
 * would get: globs, command substitution, and quoting all handled by the thing
 * that defines them. This also means the assertions below stay true for a form
 * nobody has written yet, which is the whole point of not asserting spelling.
 */
function expandArguments(argumentText) {
  const printed = execFileSync("sh", ["-c", `printf '%s\\n' ${argumentText}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
  return printed.split("\n").filter(Boolean);
}

/** The expanded argument vector for one gate, by script name. */
function runnerFiles(gate) {
  return expandArguments(runnerArgumentText(manifest.scripts[gate]));
}

/** The two scripts that invoke `node --test`, by name. */
const GATES = ["test", "test:e2e"];

test("mỗi đối số hai lệnh test đưa cho node --test đều là file test có thật", () => {
  for (const gate of GATES) {
    const files = runnerFiles(gate);
    assert.ok(
      files.length > 0,
      `"${gate}" khong khop file nao — node --test se chay 0 test roi thoat 0`,
    );
    for (const hit of files) {
      // An unmatched glob survives expansion literally in sh, so a pattern that
      // matches nothing arrives here as a path that is not on disk.
      let stat;
      try {
        stat = statSync(join(ROOT, hit));
      } catch {
        assert.fail(
          `"${hit}" trong "${gate}" khong ton tai — node --test se bao MODULE_NOT_FOUND`,
        );
      }
      assert.ok(stat.isFile(), `"${gate}" dua thu muc ${hit} cho node --test, khong phai file`);
      assert.ok(hit.endsWith(".test.mjs"), `${hit} khong phai file test`);
    }
  }
});

test("mọi file test đều có ít nhất một cổng chạy tới", () => {
  const reached = new Set(GATES.flatMap((gate) => runnerFiles(gate)));
  const missed = everyTestFile().filter((file) => !reached.has(file));
  assert.deepEqual(missed, [], `co file test khong cong nao chay toi: ${missed}`);
});

test("test:e2e chạy đúng bài end-to-end", () => {
  // The narrower gate has to reach the slice, or `npm run test:e2e` becomes a
  // command that reports success without going near the API.
  const reached = new Set(runnerFiles("test:e2e"));
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
