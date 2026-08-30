/* Refuse to measure a web export that is older than the source it claims to show.
 *
 * Every rendered gate in this directory serves a PREBUILT `expo export` and
 * reads boxes out of the browser. None of them reads a `.tsx` file. That is
 * the point -- a control that exists in the source and is off the edge of the
 * glass is a missing control, and only a render can tell you so. But it also
 * means the gate is only ever as truthful as the bundle it was pointed at,
 * and nothing in it noticed when those two drifted apart.
 *
 * bug-010019 is what that costs. A lane ran `nhom-chat-web.test.mjs` on its
 * own, which skips the `build:check` that `npm test` runs first, so the gate
 * measured a bundle built before #380 landed. It reported `KHÔNG THẤY Hỏi Rủ
 * Đi AI` at all three viewports and named a control that was present in the
 * source, mounted unconditionally, and rendered at left=10 on a fresh build.
 * The report was filed as a product defect against a screen that was correct,
 * and it blocked the team.
 *
 * The control experiment in that report is the sharp end of it. To prove the
 * defect was on `main` rather than in their branch, the lane restored one file
 * from `origin/main` and re-ran -- and got an identical failure, which read as
 * confirmation. It could not have read as anything else: the gate never opens
 * a source file, so no edit to one can move the result. A gate that cannot be
 * affected by the code it appears to be testing will agree with any theory you
 * bring it.
 *
 * So: compare the newest mtime under the source tree against the newest bundle
 * in the export, and refuse to report at all when the source is ahead. This is
 * deliberately mtime rather than a content hash, for two reasons. It works on
 * an export made by hand into `/tmp` with no stamping step, which is the path
 * the gate docstrings actually document; and `git checkout`/`git rebase` set
 * mtime to now on every file they change, so the exact command sequence in
 * bug-010019 -- rebase, then `git checkout origin/main -- TinNhan.tsx` -- trips
 * it immediately and says the true thing on the first run.
 *
 * The cost of that choice is a false "rebuild first" after a no-op touch. That
 * is the right direction to be wrong in: it spends 7 seconds, where being wrong
 * the other way spends a cross-team blocker on a button that was never broken.
 */
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/** Files that do not change what the browser is served, so their mtime must
 *  not be able to demand a rebuild. `dist-test` in particular is rewritten by
 *  `tools/fixup-esm.mjs` on the way to every run of the suite. */
const BO_QUA = new Set(["node_modules", "dist", "dist-test", ".expo", "__pycache__"]);

function moiNhat(duong, ketQua = { mtime: 0, file: null }) {
  if (!existsSync(duong)) return ketQua;
  const tin = statSync(duong);
  if (!tin.isDirectory()) {
    if (tin.mtimeMs > ketQua.mtime) return { mtime: tin.mtimeMs, file: duong };
    return ketQua;
  }
  for (const ten of readdirSync(duong)) {
    if (BO_QUA.has(ten)) continue;
    ketQua = moiNhat(join(duong, ten), ketQua);
  }
  return ketQua;
}

function gio(ms) {
  return new Date(ms).toLocaleTimeString("vi-VN", { hour12: false });
}

/**
 * Why the export at `exportDir` must not be trusted, or `null` when it may be.
 *
 * `goc` is the `apps/mobile` directory. `packages/shared` is walked too: its
 * modules are bundled, so editing one leaves the export just as stale as
 * editing a screen does.
 *
 * Returns `null` when the export is absent -- that case already has its own
 * named reason in every caller, and two reasons for one situation only makes
 * the failure harder to read.
 */
export function lyDoBanDungCu(exportDir, goc) {
  if (!existsSync(join(exportDir, "index.html"))) return null;

  const banDung = moiNhat(join(exportDir, "_expo"), moiNhat(join(exportDir, "index.html")));

  let nguon = { mtime: 0, file: null };
  for (const phan of ["src", "App.tsx", "index.ts", "app.json", "assets"]) {
    nguon = moiNhat(join(goc, phan), nguon);
  }
  nguon = moiNhat(join(goc, "..", "..", "packages", "shared"), nguon);

  if (nguon.mtime <= banDung.mtime) return null;

  return (
    `bản web ở ${exportDir} dựng lúc ${gio(banDung.mtime)}, cũ hơn nguồn ` +
    `(${nguon.file} sửa lúc ${gio(nguon.mtime)}). Gate này đo bundle chứ không đọc ` +
    `file .tsx nào, nên chạy tiếp là đo nhầm bản cũ và đổ lỗi cho màn hình. ` +
    `Dựng lại trước: npm run build:check`
  );
}
