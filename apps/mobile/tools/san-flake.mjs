/* Run the suite N times and keep the evidence of any run that is not green.
 *
 * Why this exists: a reviewer measured `727 pass / 1 fail` once on PR #312,
 * could not reproduce it in three more runs, and -- this is the part that
 * matters -- could not name the failing test. A number without a name cannot
 * be fixed, and it makes every green after it worth slightly less.
 *
 * 37 consecutive clean runs on this machine failed to reproduce it, so this is
 * not a reproduction. It is a net: the next time the suite flickers, the run
 * that flickered is on disk with the test's name pulled out of it, instead of
 * scrolling past in a terminal nobody kept.
 *
 * Deliberately runs `node --test` directly rather than `npm test`: the bundle
 * and the compiled `dist-test/` do not change between iterations, so rebuilding
 * them each time buys nothing and costs ~9s a run. Build once first:
 *
 *     npm test                              # writes .expo-build-check + dist-test
 *     node tools/san-flake.mjs 40           # then hunt
 *
 * Exit 0 means every run was green. Exit 1 means it caught one, and the log
 * path is printed. Exit 1 is the useful outcome.
 */
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const runs = Number(process.argv[2] ?? 20);
const outDir = process.env.SAN_FLAKE_DIR ?? "/tmp/san-flake";
mkdirSync(outDir, { recursive: true });

/* Same file list the `test` script uses, e2e excluded the same way. */
const list = spawnSync(
  "bash",
  ["-c", "find tests -path tests/e2e -prune -o -name '*.test.mjs' -print | sort"],
  { encoding: "utf-8" },
);
const files = list.stdout.trim().split("\n").filter(Boolean);
if (files.length === 0) {
  console.error("no test files found -- run this from apps/mobile");
  process.exit(2);
}

console.log(`săn flake: ${runs} lượt trên ${files.length} file test`);
let caught = 0;

for (let i = 1; i <= runs; i++) {
  const r = spawnSync("node", ["--test", ...files], { encoding: "utf-8" });
  const out = `${r.stdout ?? ""}${r.stderr ?? ""}`;
  const pass = /^# pass (\d+)$/m.exec(out)?.[1] ?? "?";
  const fail = /^# fail (\d+)$/m.exec(out)?.[1] ?? "?";

  /* A crashed runner reports no counts at all. That is not a green run, and
   * reading a missing number as zero is how a dead gate reads as a clean one. */
  const green = fail === "0" && pass !== "?";
  if (green) {
    console.log(`  lượt ${String(i).padStart(3)}: pass=${pass} fail=${fail}`);
    continue;
  }

  caught++;
  const names = [...out.matchAll(/^\s*not ok \d+ - (.+)$/gm)].map((m) => m[1].trim());
  const log = join(outDir, `flake-${i}.log`);
  writeFileSync(log, out);
  console.log(`  lượt ${String(i).padStart(3)}: pass=${pass} fail=${fail}  <-- BẮT ĐƯỢC`);
  for (const n of names) console.log(`      tên ca đỏ: ${n}`);
  console.log(`      log đầy đủ: ${log}`);
}

console.log(caught === 0 ? `\n${runs}/${runs} xanh, không bắt được gì.` : `\nbắt được ${caught}/${runs} lượt đỏ.`);
process.exit(caught === 0 ? 0 : 1);
