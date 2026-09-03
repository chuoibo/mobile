/* bug-010019. A rendered gate must not report on a bundle older than the source.
 *
 * The defect this pins is not in a screen. It is in what the rendered gates
 * are willing to say. `nhom-chat-web.test.mjs` serves a prebuilt `expo export`
 * and measures boxes; it opens no `.tsx` file. Run on its own -- without the
 * `build:check` that `npm test` runs first -- it will happily measure a bundle
 * from an earlier commit and announce that a control is missing from a screen
 * that renders it correctly. That is what happened: `KHÔNG THẤY Hỏi Rủ Đi AI`
 * at 320, 390 and 1280, filed against `ONhap.tsx`, where the button is mounted
 * unconditionally and sits at left=10 on a fresh build.
 *
 * Three cases, and the third is the one that keeps the fix honest:
 *
 *   A. Stale export, contents otherwise fine. The gate must refuse. Before the
 *      fix it reported a clean 7/7 -- a green verdict about a bundle that no
 *      longer matched the tree, which is the same failure wearing the opposite
 *      sign and the more dangerous of the two.
 *   B. Stale export whose bundle really is missing the label -- bug-010019
 *      reproduced exactly. The gate must blame the stale bundle and must not
 *      print `KHÔNG THẤY`, because that sentence is what sent a lane hunting
 *      through a correct component.
 *   C. Fresh export. The gate must still pass 7/7. Without this case, "refuse
 *      everything" would satisfy A and B, and a gate that never reports is not
 *      a stricter gate, it is a deleted one.
 *
 * These drive the real gate as a subprocess rather than calling the guard
 * directly, because the defect was never in the arithmetic of a comparison --
 * it was that no gate performed one. A unit test of `lyDoBanDungCu` would have
 * passed on the day the bug was filed.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, describe, test } from "node:test";

import { findChrome } from "./chrome-cdp.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const MOBILE = join(HERE, "..");
const THAT = join(MOBILE, ".expo-build-check");
const GATE = "tests/nhom-chat-web.test.mjs";

/** The label as it survives an Expo web build. Vietnamese reaches the bundle
 *  `\u`-escaped, so the raw string finds nothing -- searching for it and
 *  reading zero hits as "the button is gone" is its own way to file this bug. */
const NHAN_TRONG_BUNDLE = "H\\u1ecfi R\\u1ee7 \\u0110i AI";

const CU = new Date("2020-01-01T00:00:00Z");

const nhaTam = [];

/** Trang nháp mà một ca KHÁC ghi vào cùng thư mục export.
 *
 * `duong-vao-mon-cua-toi.test.mjs` ghi `__mon-cua-toi-*.html` thẳng vào
 * `.expo-build-check` — bắt buộc, vì chúng phải nạp bundle bằng đường tương
 * đối từ chính gốc đó — rồi xoá đi khi xong. `node --test` chạy các file test
 * SONG SONG, nên bản sao ở đây và cú xoá ở đó chạy cùng lúc trên một thư mục.
 *
 * Đo trên CI ngày 2026-09-03: `cpSync` đọc được tên trong `readdir` rồi
 * `lstat` chính nó và ăn ENOENT — `no such file or directory, lstat
 * '.../.expo-build-check/__mon-cua-toi-ma-tran.html'`. Cổng này đỏ vì một ca
 * khác dọn dẹp đúng lúc, chứ không phải vì bản export sai.
 *
 * Bỏ qua chúng là đúng chứ không phải né: chúng KHÔNG thuộc bản export đang
 * được xét. Cái cổng này hỏi là bản dựng có cũ hơn nguồn không, và một trang
 * nháp của ca khác không trả lời câu đó.
 */
const TRANG_NHAP = /(^|[\\/])__[^\\/]*\.html$/;

function banSaoCu(doi) {
  const dich = mkdtempSync(join(tmpdir(), "export-cu-"));
  nhaTam.push(dich);
  // Thử lại một lần: `filter` chặn được những trang nháp đã biết tên, nhưng
  // cuộc đua thì không chỉ có chúng — một file bất kỳ biến mất giữa `readdir`
  // và `lstat` vẫn ném. Một lượt nữa trên một thư mục đã yên là đủ, và nếu
  // vẫn ném thì để nó ném: che luôn lần hai là biến cổng thành đồ trang trí.
  for (let lan = 0; ; lan++) {
    try {
      cpSync(THAT, dich, { recursive: true, filter: (tu) => !TRANG_NHAP.test(tu) });
      break;
    } catch (loi) {
      if (loi.code !== "ENOENT" || lan > 0) throw loi;
    }
  }
  if (doi) doi(dich);
  luiGio(dich);
  return dich;
}

/** Backdate the copy instead of touching `src`. The tree under test must come
 *  out of this file exactly as it went in; a gate run that leaves the working
 *  copy dirty is a gate that changes the next answer it gives. */
function luiGio(duong) {
  const tin = statSync(duong);
  if (tin.isDirectory()) for (const ten of readdirSync(duong)) luiGio(join(duong, ten));
  utimesSync(duong, CU, CU);
}

function boNhanTrongBundle(goc) {
  const thuMuc = join(goc, "_expo", "static", "js", "web");
  let doi = 0;
  for (const ten of readdirSync(thuMuc)) {
    const duong = join(thuMuc, ten);
    const ma = readFileSync(duong, "utf8");
    if (!ma.includes(NHAN_TRONG_BUNDLE)) continue;
    doi += ma.split(NHAN_TRONG_BUNDLE).length - 1;
    writeFileSync(duong, ma.split(NHAN_TRONG_BUNDLE).join("NHAN-DA-BI-DOI-DE-GIA-LAP"));
  }
  assert.ok(doi > 0, "không thấy nhãn trong bundle để giả lập bản cũ thiếu nút");
  return doi;
}

function chayGate(exportDir) {
  const moi = { ...process.env, MOBILE_WEB_EXPORT: exportDir, MOBILE_REQUIRE_WEB_A11Y: "1" };
  // `node --test` marks its children with `NODE_TEST_CONTEXT`, and a run that
  // inherits it reports to a parent runner instead of to stdout: no `# fail`
  // summary, and an exit code that means "results were forwarded" rather than
  // "the suite passed". Inheriting it here read as case C going red and as the
  // stale-bundle runs exiting 0 -- both of them measurements of the harness,
  // not of the gate.
  delete moi.NODE_TEST_CONTEXT;

  const ket = spawnSync(process.execPath, ["--test", GATE], {
    cwd: MOBILE,
    encoding: "utf8",
    env: moi,
    timeout: 180_000,
  });
  return { ma: ket.status, ra: `${ket.stdout ?? ""}${ket.stderr ?? ""}` };
}

const lyDo = [];
if (!existsSync(join(THAT, "index.html"))) lyDo.push(`chưa có bản web ở ${THAT} (chạy: npm run build:check)`);
if (!findChrome()) lyDo.push("không tìm thấy Chrome (đặt CHROME_BIN, hoặc cài qua playwright)");

if (lyDo.length) {
  test(`cổng web không đọc bản cũ — BỎ QUA: ${lyDo.join("; ")}`, { skip: lyDo.join("; ") }, () => {});
} else {
  describe("cổng web phải từ chối bản export cũ hơn nguồn", () => {
    after(() => {
      for (const d of nhaTam) rmSync(d, { recursive: true, force: true });
    });

    test("A. bản cũ nhưng nội dung còn tốt: không được báo xanh", () => {
      const { ma, ra } = chayGate(banSaoCu(null));
      console.log(`  mã thoát: ${ma}`);
      assert.match(
        ra,
        /cũ hơn nguồn/,
        "cổng đo một bundle cũ hơn cây nguồn mà không nói ra; đây là dấu xanh cho bản không còn khớp",
      );
      assert.notEqual(ma, 0, "cổng thoát 0 trên bản export đã cũ");
    });

    test("B. bản cũ thiếu nhãn (bug-010019): đổ lỗi cho bundle, không cho màn hình", () => {
      const { ma, ra } = chayGate(banSaoCu((d) => console.log(`  đã đổi ${boNhanTrongBundle(d)} chỗ trong bundle`)));
      console.log(`  mã thoát: ${ma}`);
      assert.match(ra, /cũ hơn nguồn/, "không nói bundle đã cũ");
      assert.doesNotMatch(
        ra,
        /KHÔNG THẤY/,
        "cổng vẫn vu cho một control là không tồn tại, trong khi nguyên nhân là bundle cũ",
      );
      assert.notEqual(ma, 0, "cổng thoát 0 trên bản export đã cũ");
    });

    test("C. bản dựng đúng từ cây này: cổng vẫn chạy và vẫn xanh", () => {
      const { ma, ra } = chayGate(THAT);
      const dong = ra.match(/^# (?:tests|pass|fail) \d+$/gm) ?? [];
      console.log(`  ${dong.join("  ")}`);
      assert.doesNotMatch(ra, /cũ hơn nguồn/, "bản vừa dựng từ cây này lại bị coi là cũ");
      assert.match(ra, /^# fail 0$/m, "cổng không còn xanh trên bản dựng đúng");
      assert.equal(ma, 0, `cổng thoát ${ma} trên bản dựng đúng`);
    });
  });
}
