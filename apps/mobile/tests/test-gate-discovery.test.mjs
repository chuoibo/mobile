/* The test gate has to actually run the tests. That is not automatic.
 *
 * `node --test tests/` reads its positional argument as a directory to recurse
 * on Node 20, and as a glob pattern on Node 22. So the same line that runs 40
 * tests on one machine dies with MODULE_NOT_FOUND on the other, and every
 * obvious repair trades that crash for something quieter and worse:
 *
 *   node --test "tests/**\/*.test.mjs"   Node 20 has no glob support, so this
 *                                        matches no file, runs no test, and
 *                                        exits 0. A green gate that proved
 *                                        nothing is worse than a red one.
 *   node --test tests/*.test.mjs         The shell expands one level only, so
 *                                        tests/e2e/ is dropped without a word.
 *   node --test tests/*.test.mjs tests/e2e/*.test.mjs
 *                                        Correct today, and silently stops
 *                                        covering the next directory somebody
 *                                        adds.
 *
 * All four failures look identical from the outside: exit 0, no complaint. So
 * this file does not check the command's spelling, which would only encode
 * today's answer. It takes the command out of package.json, points it at a
 * fixture tree whose contents are known, and asserts on which files actually
 * executed. A form that skips a directory fails here even when it exits 0.
 *
 * One directory is excluded from `npm test` on purpose: `tests/e2e/` talks to a
 * real API server, so folding it into the default gate made the gate answer
 * differently on identical code depending on whether some other worktree
 * happened to be serving on port 8099. A gate that changes its mind while the
 * code stands still teaches people to rerun until green. It lives behind
 * `npm run test:e2e` instead, where `MOBILE_REQUIRE_E2E=1` turns a missing
 * server into a failure rather than a skip.
 *
 * That exclusion is exactly how coverage holes get in, so it is not taken on
 * trust: the third test asserts the *union* of the two gates reaches every test
 * file. A file no gate runs fails here, whichever gate was supposed to own it.
 *
 * Run from apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const PACKAGE_JSON = join(dirname(fileURLToPath(import.meta.url)), "..", "package.json");

/* The fixture mirrors the shape of the real tests/ directory rather than its
 * contents: one file at the top, one under the e2e/ directory that belongs to
 * the second gate, and one nested deeper under a directory name nothing
 * hard-codes. The third is the one that fails a command holding a literal list
 * of directories. `helper.mjs` is the shared module that is not a test and must
 * not be executed as one. */
const E2E_FILE = "e2e/beta.test.mjs";
const TEST_FILES = ["alpha.test.mjs", E2E_FILE, "nested/deep/gamma.test.mjs"];
const DEFAULT_GATE_FILES = TEST_FILES.filter((file) => file !== E2E_FILE);
const HELPER = "helper.mjs";

function markerFor(file) {
  return file.replaceAll("/", "-");
}

/* Marker written from inside the test body, not at module scope: loading a file
 * is not the same as running what is in it, and the gate is only worth having
 * if the assertions ran. Every marker lands flat in the fixture root, so the
 * path climbs back out by however deep the file sits under it. */
function testFileSource(file) {
  const marker = "../".repeat(file.split("/").length) + markerFor(file);
  return [
    'import test from "node:test";',
    'import { writeFileSync } from "node:fs";',
    "",
    `test(${JSON.stringify(markerFor(file))}, () => {`,
    `  writeFileSync(new URL(${JSON.stringify(marker)}, import.meta.url), "");`,
    "});",
    "",
  ].join("\n");
}

function buildFixture() {
  const root = mkdtempSync(join(tmpdir(), "test-gate-"));
  for (const file of TEST_FILES) {
    const path = join(root, "tests", file);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, testFileSource(file));
  }
  // Top-level write, not a test: this one records merely being loaded.
  writeFileSync(
    join(root, "tests", HELPER),
    `import { writeFileSync } from "node:fs";\nwriteFileSync(new URL("../${HELPER}.ran", import.meta.url), "");\n`,
  );
  return root;
}

/* package.json scripts are `&&`-chains; the piece under test is the one that
 * invokes the runner. Pulled out by hand rather than running the whole script,
 * because the rest of the chain compiles TypeScript the fixture does not have. */
function runnerCommand(script) {
  const segments = script.split("&&").map((segment) => segment.trim());
  const found = segments.filter((segment) => /^node .*--test\b/.test(segment));
  assert.equal(found.length, 1, `expected exactly one \`node --test\` step in: ${script}`);
  return found[0];
}

function runGate(command, cwd) {
  // NODE_TEST_CONTEXT is set by the runner that is executing *this* file. Left
  // in place it puts the child into child-process reporting mode, so strip it:
  // the child has to behave the way it does when a person types the command.
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  try {
    execFileSync("sh", ["-c", command], { cwd, env, stdio: "pipe" });
    return 0;
  } catch (error) {
    return error.status ?? 1;
  }
}

function scripts() {
  return JSON.parse(readFileSync(PACKAGE_JSON, "utf8")).scripts;
}

test("npm test runs every test file outside tests/e2e, including nested ones", () => {
  const root = buildFixture();
  try {
    const command = runnerCommand(scripts().test);
    const status = runGate(command, root);

    const missing = DEFAULT_GATE_FILES.filter((file) => !existsSync(join(root, markerFor(file))));
    assert.deepEqual(
      missing,
      [],
      `\`${command}\` exited ${status} without running: ${missing.join(", ")}`,
    );
    assert.equal(status, 0, `\`${command}\` exited ${status}`);
    assert.ok(
      !existsSync(join(root, markerFor(E2E_FILE))),
      `\`${command}\` ran ${E2E_FILE}; the default gate must not need a live server`,
    );
    assert.ok(
      !existsSync(join(root, `${HELPER}.ran`)),
      `\`${command}\` executed ${HELPER}, which is a shared module and not a test`,
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("npm run test:e2e runs the end-to-end files and nothing else", () => {
  const root = buildFixture();
  try {
    const command = runnerCommand(scripts()["test:e2e"]);
    const status = runGate(command, root);

    assert.ok(
      existsSync(join(root, markerFor("e2e/beta.test.mjs"))),
      `\`${command}\` exited ${status} without running tests/e2e/beta.test.mjs`,
    );
    assert.equal(status, 0, `\`${command}\` exited ${status}`);
    assert.ok(
      !existsSync(join(root, markerFor("alpha.test.mjs"))),
      `\`${command}\` reached outside tests/e2e/`,
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

/* Splitting the suite across two gates is what creates the room for a file no
 * gate runs. Neither test above can see that hole on its own: each one only
 * knows the files it expects to own. Running both against one fixture and
 * asserting on the union is the check that actually closes it, and it stays
 * true no matter how the two commands are later spelled or where the boundary
 * between them is drawn. */
test("the two gates together reach every test file", () => {
  const root = buildFixture();
  try {
    const commands = [runnerCommand(scripts().test), runnerCommand(scripts()["test:e2e"])];
    const statuses = commands.map((command) => runGate(command, root));

    const unreached = TEST_FILES.filter((file) => !existsSync(join(root, markerFor(file))));
    assert.deepEqual(
      unreached,
      [],
      `no gate ran: ${unreached.join(", ")} — ` +
        commands.map((command, i) => `\`${command}\` exited ${statuses[i]}`).join("; "),
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
