/* Does this branch re-deliver work that is already on the base branch?
 *
 * This repo merges with SQUASH. When a parent PR lands, its individual commits
 * stop existing on the base branch: all their content arrives as one new commit
 * with a new hash. A stacked child branch still carries the originals, so git
 * compares two unrelated histories that happen to touch the same files and
 * reports "changed in both" on files whose CONTENT IS IDENTICAL on both sides.
 *
 * The damage is not the conflict, which is loud. It is the quiet half: the
 * child's PR shows a diff containing the parent's whole feature, so a reviewer
 * reads several thousand lines that nobody wrote in that PR, and any real
 * change hides inside them. #82 showed +5128/-89 across 25 files when its
 * actual work was one screen.
 *
 * The signature is exact and needs no heuristic: a file that appears in
 * `git diff base...ref` while `ref:file` and `base:file` hash to the same blob
 * is a file the PR claims to change and does not. Zero of those is the property
 * a stacked branch must hold; anything above zero means it was merged onto the
 * base instead of rebased onto it.
 *
 * Three-dot on purpose -- `base...ref` diffs from the merge base to the ref,
 * which is what GitHub renders in "Files changed". Two-dot would compare tips
 * and could never show this, so a two-dot check would pass on the broken branch.
 *
 * Usage:
 *   node tools/stacked-branch-check.mjs                  # HEAD vs origin/main
 *   node tools/stacked-branch-check.mjs <ref> <base>
 * Exit 0 clean, 2 redundant files found, 1 could not run.
 */
import { execFileSync } from "node:child_process";

/** Run git, returning stdout trimmed, or null when the command fails. */
function git(args, cwd) {
  try {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

/** Whether a revision can be resolved at all, so a miss is not read as clean. */
export function revExists(rev, cwd) {
  return git(["rev-parse", "--verify", "--quiet", `${rev}^{commit}`], cwd) !== null;
}

/**
 * Files the PR shows as changed whose content already matches the base.
 *
 * Deleted-on-ref files resolve to null and are skipped: a deletion is a real
 * change, and `null === null` would otherwise mark every one of them redundant.
 */
export function redundantFiles({ base = "origin/main", ref = "HEAD", cwd } = {}) {
  const listed = git(["diff", "--name-only", `${base}...${ref}`], cwd);
  if (listed === null) return null;
  const changed = listed.split("\n").filter(Boolean);
  return changed.filter((file) => {
    const onRef = git(["rev-parse", `${ref}:${file}`], cwd);
    if (onRef === null) return false;
    return onRef === git(["rev-parse", `${base}:${file}`], cwd);
  });
}

/** Every file the PR shows as changed, redundant or not. */
export function changedFiles({ base = "origin/main", ref = "HEAD", cwd } = {}) {
  const listed = git(["diff", "--name-only", `${base}...${ref}`], cwd);
  return listed === null ? null : listed.split("\n").filter(Boolean);
}

/**
 * Name which of the two redundancy shapes this is, because they need opposite
 * instructions and only the count can tell them apart.
 *
 * A stacked child that merged the base in keeps its own commit, so its real
 * work survives in the diff: some files are redundant, at least one is not.
 * A branch whose work has already landed by squash carries nothing new at all
 * -- every file in the diff hashes to the base. The old message assumed the
 * first shape and sent the second one to `git rebase --onto <parent tip>`,
 * which is wrong twice over: there is no parent PR to name, and rebasing a
 * branch that is already merged replays nothing and leaves it empty.
 *
 * This is not hypothetical. A gate run on 2026-08-30 hit "9/9 file ... y het
 * origin/main" a few minutes after that branch's own PR was squash-merged, and
 * the advice it printed pointed at a stack that never existed.
 */
export function diagnose({ redundant, changed, base = "origin/main" } = {}) {
  const counts = `${redundant.length}/${changed.length} file hien trong diff ma ` +
    `noi dung y het ${base}.`;

  if (redundant.length === 0) {
    return { kind: "clean", message: "" };
  }

  // Every changed file identical to the base: the diff adds nothing over it.
  if (redundant.length === changed.length) {
    return {
      kind: "merged",
      message:
        `${counts} Nhanh nay khong con gi moi so voi ${base} -- viec cua no da ` +
        `nam tren ${base} roi (thuong la vua duoc squash-merge). Khong phai ` +
        `loi: dung rebase, chi can sang ${base} va mo nhanh moi tu do.`,
    };
  }

  return {
    kind: "stacked",
    message:
      `${counts} Nhanh nay dang merge ${base} vao thay vi rebase len no. ` +
      `Sua: git rebase --onto ${base} <commit cuoi cua PR cha>`,
  };
}

const invokedDirectly =
  process.argv[1] && import.meta.url === `file://${process.argv[1]}`;

if (invokedDirectly) {
  const ref = process.argv[2] ?? "HEAD";
  const base = process.argv[3] ?? "origin/main";
  if (!revExists(base) || !revExists(ref)) {
    console.error(
      `khong giai duoc ref: base=${base} ref=${ref}. ` +
        "Chay `git fetch origin main` truoc.",
    );
    process.exit(1);
  }
  const redundant = redundantFiles({ base, ref });
  const changed = changedFiles({ base, ref });
  console.log(
    JSON.stringify(
      { base, ref, changed: changed.length, redundant },
      null,
      2,
    ),
  );
  if (redundant.length > 0) {
    console.error(`\n${diagnose({ redundant, changed, base }).message}`);
    process.exit(2);
  }
}
