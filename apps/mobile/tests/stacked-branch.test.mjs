/* The squash-stacking trap, reproduced in a repo built for the purpose.
 *
 * This bit twice in one day: #81 and #82. The mechanism is in
 * `tools/stacked-branch-check.mjs`; what this file proves is that the checker
 * actually goes red on the broken shape, because a checker for a structural
 * problem is exactly the kind that can be written wrong and never noticed --
 * it returns "0 redundant files" on a healthy branch whether it works or not.
 *
 * So the first test builds the failure. A parent branch is squash-merged into
 * main, a child stacked on the parent merges main back in the way that feels
 * natural and is wrong, and the checker must report the parent's files as
 * redundant. Then the same child is rebased with `--onto`, and the same
 * checker on the same repo must report none. Red then green, in one test, on a
 * repo that exists only inside it -- no network, no fixture, nothing to drift.
 *
 * The second test is the live guard: this branch, against origin/main, right
 * now. It skips when origin/main is not fetched rather than passing, because
 * "the base ref is missing" and "the branch is clean" are the same silence and
 * only one of them is good news.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  changedFiles,
  redundantFiles,
  revExists,
} from "../tools/stacked-branch-check.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const REPO = dirname(dirname(ROOT));

/**
 * Identity passed per-command so the test does not depend on a global config.
 *
 * `user.email` is deliberately not address-shaped. Git never validates the
 * field, and the repo guard refuses any staged diff containing something that
 * parses as an email -- correctly, since it cannot tell a placeholder from a
 * participant's real address. Writing a name here rather than allowlisting a
 * fake address keeps that guard at full strength.
 */
const IDENT = [
  "-c",
  "user.email=gate-fixture",
  "-c",
  "user.name=gate",
  "-c",
  "commit.gpgsign=false",
];

function run(cwd, ...args) {
  return execFileSync("git", [...IDENT, ...args], {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function commit(cwd, file, body, message) {
  writeFileSync(join(cwd, file), body);
  run(cwd, "add", file);
  run(cwd, "commit", "-m", message);
}

/**
 * A repo shaped exactly like this one at the moment #82 broke.
 *
 * main:   A ── M1 ─────────────── S(squash of parent)
 *          \     \
 * parent:   P1 ── P2
 *                  \
 * child:            C1 ── M(merge cua main@M1)
 *
 * The merge of main@M1 is the reflex being reproduced, and the reason it is
 * in the fixture rather than left out: it is what everybody tries first, it
 * resolves cleanly, and it does not help. It moves the merge base up to M1,
 * which is still older than the squash S -- so the parent's files stay in the
 * child's diff, byte-identical to main, exactly as GitHub rendered them.
 *
 * Merging main *after* S would hide the trap instead of showing it: the merge
 * base would become the tip and the diff would shrink to the child's own work
 * for the wrong reason. That is the shape this fixture must not have.
 */
function buildSquashStack() {
  const dir = mkdtempSync(join(tmpdir(), "stacked-branch-"));
  run(dir, "init", "--quiet", "--initial-branch=main");
  commit(dir, "base.ts", "export const base = 1;\n", "A");

  run(dir, "switch", "--quiet", "-c", "parent");
  commit(dir, "shared.ts", "export const shared = 'cha';\n", "P1");
  commit(dir, "shared-two.ts", "export const two = 2;\n", "P2");
  const parentTip = run(dir, "rev-parse", "HEAD");

  run(dir, "switch", "--quiet", "-c", "child");
  commit(dir, "child.ts", "export const child = 'con';\n", "C1");

  // main moves on while the stack is open, and the child merges that state.
  run(dir, "switch", "--quiet", "main");
  commit(dir, "ci.ts", "export const ci = true;\n", "M1");
  run(dir, "switch", "--quiet", "child");
  run(dir, "merge", "--no-edit", "-m", "merge main vao con", "main");

  // The squash merge: main gains the parent's content, loses its commits.
  run(dir, "switch", "--quiet", "main");
  run(dir, "merge", "--squash", "parent");
  run(dir, "commit", "-m", "S: squash cua parent");

  run(dir, "switch", "--quiet", "child");
  return { dir, parentTip };
}

test("cổng bắt được nhánh con mang lại nguyên phần cha đã squash", () => {
  const { dir, parentTip } = buildSquashStack();
  try {
    // Red half: the child has already merged main, the way everybody tries
    // first, and the parent's files are still sitting in its diff.
    const redundant = redundantFiles({ base: "main", ref: "HEAD", cwd: dir });
    const changed = changedFiles({ base: "main", ref: "HEAD", cwd: dir });

    assert.deepEqual(
      redundant.sort(),
      ["shared-two.ts", "shared.ts"],
      "hai file cua nhanh cha phai bi bao la trung: chung hien trong diff " +
        "cua PR con nhung noi dung y het main",
    );
    assert.ok(
      changed.includes("child.ts"),
      "viec that cua nhanh con phai van nam trong diff",
    );
    assert.ok(
      !redundant.includes("child.ts"),
      "viec that cua nhanh con khong duoc bi bao la trung",
    );

    // Green half: same repo, same checker, rebased the way the rule says.
    // The merge commit and M1 both drop out -- M1 because it is already on
    // main, the merge because a rebase replays commits, not merges.
    run(dir, "rebase", "--onto", "main", parentTip);

    assert.deepEqual(
      redundantFiles({ base: "main", ref: "HEAD", cwd: dir }),
      [],
      "sau `rebase --onto` thi khong con file nao trung",
    );
    assert.deepEqual(
      changedFiles({ base: "main", ref: "HEAD", cwd: dir }),
      ["child.ts"],
      "diff phai chi con dung viec cua nhanh con",
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("nhánh này không mang lại file nào đã có nguyên vẹn trên origin/main", (t) => {
  if (!revExists("origin/main", REPO)) {
    t.skip("chua co origin/main trong clone nay — chay `git fetch origin main`");
    return;
  }
  const redundant = redundantFiles({ base: "origin/main", ref: "HEAD", cwd: REPO });
  const changed = changedFiles({ base: "origin/main", ref: "HEAD", cwd: REPO });
  assert.deepEqual(
    redundant,
    [],
    `${redundant.length}/${changed.length} file hien trong diff ma noi dung y het ` +
      "origin/main. Nhanh nay dang merge main vao thay vi rebase len main; " +
      "chay `git rebase --onto origin/main <commit cuoi cua PR cha>`",
  );
});
