/** Prove the `anh` column of `quet-tab-url.mjs` is a gate and not decoration.
 *
 * This file exists because of a specific failure, and the failure is worth
 * stating because the gate LOOKED fine on both sides of it.
 *
 * `quet-tab-url.mjs` asserts that named screens show a decoded photograph. The
 * first version counted `imgs.filter((i) => i.naturalWidth > 0).length`, and
 * that number was a lie on every row it appeared in. react-native-web renders
 * `<Image>` as TWO nodes: an `<img>` pinned at `opacity: 0` whose only job is
 * to decode and fire `onLoad`, and a wrapper `<div>` that paints the picture
 * through an inline `background-image`. The stub answered the `<img>`, so
 * `naturalWidth` came back 480 while the div dialled the API host on the real
 * network and got nothing. Every place card drew its category ramp under a
 * column reading "1 anh giai ma duoc".
 *
 * So a green from that column proved nothing, and no amount of re-running it
 * would have said so. What says so is breaking the painting on purpose and
 * checking the column notices. That is what this file does.
 *
 *     cd apps/mobile && npm run build:check && node tools/dot-bien-anh-ve.mjs
 *
 * ## Two kinds of row, and the second kind is the point
 *
 * `canBat` rows break the painting and REQUIRE the gate to go red naming the
 * screen. `canMu` rows break the painting the same way but also put the OLD
 * measure back, and require the gate to stay GREEN -- they are the control
 * that shows the old column could not see this class of breakage at all. A
 * table of nothing but red rows cannot distinguish "the gate works" from "the
 * gate reddens at anything"; the pair can.
 *
 * ## Red for the wrong reason is a miss, not a catch
 *
 * A mutation that trips an unrelated assertion, or throws a ReferenceError,
 * exits non-zero and reads exactly like a gate that caught something. So each
 * row declares the sentence it expects, and red without that sentence is
 * reported as `DO NHAM LY DO` and counted as a miss.
 *
 * ## Why one row costs two edits
 *
 * The scan throws on the FIRST screen that fails, and `kham-pha` is scanned
 * before `dia-diem`. A single global break therefore always trips `kham-pha`
 * and the heaviest photo frame in the app -- `dia-diem`, 248pt full bleed, the
 * screen the original defect was reported against -- is never reached. So the
 * row that aims at it first drops the `anh` expectation from the rows ahead of
 * it. Covering only the shape that happens to be scanned first is how a canary
 * ends up vouching for screens it never ran on.
 *
 * ## A refusal to run is not a pause, it is an expiry
 *
 * The control row M4 was green when this file was written, and went stale
 * without anyone touching it: `album-mot` arrived in the scan list later, and
 * it draws two frames while decoding one, so the node-counting measure the
 * control restores answers 2 against an expectation of 1. From then on M4 was
 * red for a reason it was not asking about.
 *
 * Nothing reported that, because by then the tool had stopped running at all.
 * Two `low-contrast` findings on `doc-bill` had made the baseline red, and the
 * guard above throws `nen sach da do san` rather than score a table against a
 * red tree. That guard is right, and it is still the better of the two
 * failures. But the cost is worth naming: while a tool refuses to run, the
 * things inside it keep going out of date, and it comes back not where it was
 * left but wherever the codebase drifted to. The refusal was loud; what it was
 * protecting was quietly rotting behind it. So the first clean run after an
 * outage should be read as a first run, not as a resumption.
 */
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, "..");
const QUET = path.join(MOBILE, "tools/quet-tab-url.mjs");
const STUB = path.join(MOBILE, "tools/tab-snapshots.mjs");

/** Disable the half of the stub that serves the element which actually PAINTS.
 *  This is the exact wiring whose absence produced the original false green. */
const TAT_VE = {
  file: STUB,
  neo: `    const veLai = (el) => {
      if (!el || el.nodeType !== 1 || !el.getAttribute) return;`,
  thay: `    const veLai = (el) => {
      if (1) return; /* dot-bien: khong phuc vu cai VE */
      if (!el || el.nodeType !== 1 || !el.getAttribute) return;`,
};

/** Put the pre-fix measure back: count candidate frames instead of asking the
 *  pixels which of them showed anything. */
const DEM_CU = {
  file: QUET,
  neo: "    const anh = await demAnhVeDuoc(page, r.khung);",
  thay: "    const anh = r.khung.length; /* dot-bien: dem node, khong dem pixel */",
};

/** Steering for the control row, for the reason given under "Why one row costs
 *  two edits" -- but aimed at a screen rather than an ordering.
 *
 *  `album-mot` draws TWO frames and decodes ONE on purpose: the stub holds
 *  bytes for `...0002` and not for `...0004`, and `anh: 1` is the honest count
 *  of what a reader actually sees. Swap the measure for node-counting and that
 *  same screen answers 2, which trips the "Thừa ảnh" branch of the exact-count
 *  assertion -- a red that says the counter changed, not that the painting
 *  broke. Left in, it makes the control red for a reason the control is not
 *  asking about, and by this file's own rule that is a miss.
 *
 *  So the control aligns this one row to what node-counting reports, leaving
 *  the broken painting as the only thing still available for the gate to see.
 *  Measured: with this edit the mutated scan ends `tong findings: 0`, exit 0 --
 *  the painting is off and the old measure calls it fine, which is the whole
 *  claim. `album-phim` is deliberately NOT touched; it draws one frame and
 *  decodes it, so node-counting already agrees with it, and moving it to 2
 *  produces `album-phim: can 2, dang co 1` -- measured, on the first attempt at
 *  this fix. */
const KHUNG_THUA_ALBUM = {
  file: STUB,
  neo: `    needle: "Tên album là tên chuyến",
    anh: 1,`,
  thay: `    needle: "Tên album là tên chuyến",
    anh: 2, /* dot-bien: bang so KHUNG, vi cot dang dem node */`,
};

const DOT_BIEN = [
  {
    ten: "M1 · gỡ phần stub phục vụ cái VẼ",
    kieu: "canBat",
    sua: [TAT_VE],
    mongDoi: "kham-pha: can 1 anh giai ma duoc, dang co 0",
  },
  {
    ten: "M2 · byte PNG rỗng, ảnh không giải mã được",
    kieu: "canBat",
    sua: [
      {
        file: STUB,
        neo: "    b64: pngThuBytes(480, 360, { dayChoi: true }).toString(\"base64\"),",
        thay: "    b64: \"\", /* dot-bien: khong co byte anh */",
      },
    ],
    mongDoi: "kham-pha: can 1 anh giai ma duoc, dang co 0",
  },
  {
    // The heaviest photo frame in the app, and the screen the defect report
    // named. Reached only by silencing the two image rows scanned before it.
    ten: "M3 · cùng vết đứt, nhưng để màn chi tiết dia-diem là màn đỏ đầu tiên",
    kieu: "canBat",
    sua: [
      TAT_VE,
      {
        file: STUB,
        neo: 'needle: "Tiệm Nướng Xóm Lào", anh: 1, chuTrenAnh: true },',
        thay: 'needle: "Tiệm Nướng Xóm Lào", chuTrenAnh: true },',
      },
      {
        file: STUB,
        neo: 'needle: "Đã đi cùng nhau", anh: 1 },',
        thay: 'needle: "Đã đi cùng nhau" },',
      },
    ],
    mongDoi: "dia-diem: can 1 anh giai ma duoc, dang co 0",
  },
  {
    // The control. Same breakage as M1, measured the way the column measured
    // before the fix. A green here is the evidence that the old column was
    // decoration -- and that the red rows above are not free.
    ten: "M4 · CHỨNG: cùng vết đứt của M1, đo bằng cột `anh` cũ (đếm node)",
    kieu: "canMu",
    sua: [TAT_VE, DEM_CU, KHUNG_THUA_ALBUM],
    mongDoi: null,
  },
];

function chay() {
  const r = spawnSync("node", ["tools/quet-tab-url.mjs"], {
    cwd: MOBILE,
    encoding: "utf8",
    env: process.env,
    maxBuffer: 64 * 1024 * 1024,
  });
  return { ma: r.status, ra: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}

function khoiPhuc() {
  // Safe only because the baseline is COMMITTED. Run against a dirty tree this
  // would delete the very fix being measured -- that has happened here before.
  execFileSync("git", ["checkout", "--", QUET, STUB], { cwd: MOBILE });
}

if (!process.env.PUPPETEER_EXECUTABLE_PATH) {
  // Without a browser the scan returns 0 findings and exits 0 on every page,
  // which is byte-identical to a clean run. Refuse rather than report that.
  throw new Error("can PUPPETEER_EXECUTABLE_PATH -- thieu Chrome thi moi luot deu 'sach'");
}

const sach = chay();
console.log(`nen sach: ma=${sach.ma} (can 0)`);
if (sach.ma !== 0) {
  console.log(sach.ra.slice(-2000));
  throw new Error("nen sach da do san -- moi con so duoi deu vo nghia");
}

let bat = 0;
for (const m of DOT_BIEN) {
  const goc = new Map();
  for (const s of m.sua) {
    if (!goc.has(s.file)) goc.set(s.file, fs.readFileSync(s.file, "utf8"));
  }
  for (const s of m.sua) {
    const trc = fs.readFileSync(s.file, "utf8");
    const soLan = trc.split(s.neo).length - 1;
    if (soLan !== 1) {
      // Not a warning. An anchor that is missing or doubled means this mutation
      // did not test what its name claims, so the run has no result to report.
      khoiPhuc();
      throw new Error(
        `${m.ten}: neo xuat hien ${soLan} lan trong ${path.basename(s.file)}, can dung 1`,
      );
    }
    fs.writeFileSync(s.file, trc.replace(s.neo, s.thay));
  }
  for (const [f, truoc] of goc) {
    if (fs.readFileSync(f, "utf8") === truoc) {
      khoiPhuc();
      throw new Error(`${m.ten}: ghi xong ma ${path.basename(f)} khong doi`);
    }
  }

  const r = chay();
  let ket;
  if (m.kieu === "canMu") {
    // Green is the expected result here, and it is the finding.
    ket = r.ma === 0 ? "XANH dung du kien (cot cu MU voi vet dut nay)" : "DO ngoai du kien";
    if (r.ma === 0) bat++;
  } else {
    const dungLyDo = r.ra.includes(m.mongDoi);
    ket = r.ma === 0 ? "XANH (CONG MU)" : dungLyDo ? "DO dung ly do" : "DO NHAM LY DO";
    if (r.ma !== 0 && dungLyDo) bat++;
    if (r.ma !== 0 && !dungLyDo) {
      console.log(`    mong doi: ${m.mongDoi}`);
      const dong = r.ra.split("\n").filter((l) => /Error:|anh giai ma duoc/.test(l));
      console.log(dong.slice(0, 5).map((l) => `    got: ${l.trim().slice(0, 160)}`).join("\n"));
    }
  }
  console.log(`${m.ten}\n    -> ${ket}  (ma=${r.ma})`);
  khoiPhuc();
}

const lai = chay();
console.log(`\nsau khi khoi phuc: ma=${lai.ma} (can 0)`);
console.log(`dung du kien: ${bat}/${DOT_BIEN.length}`);
process.exitCode = bat === DOT_BIEN.length && lai.ma === 0 ? 0 : 1;
