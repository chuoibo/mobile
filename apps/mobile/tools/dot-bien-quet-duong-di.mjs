/** Prove `tests/quet-man-sau-tap.test.mjs` is a gate and not decoration.
 *
 * A gate that has only ever been green is indistinguishable from a gate that
 * cannot go red. Worse, this repo has repeatedly produced gates that DO go red
 * -- for the wrong reason. A mutation that trips an unrelated assertion, or
 * throws a ReferenceError, reports `fail` and reads exactly like a gate that
 * caught something.
 *
 * So each mutation here declares the sentence it expects to see. Red without
 * that sentence is reported as `DO NHAM LY DO` and counts as a miss, the same
 * as green.
 *
 *     node tools/dot-bien-quet-duong-di.mjs
 */
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, "..");
const SCAN = path.join(MOBILE, "tools/quet-man-sau-tap.mjs");
const WALK = path.join(MOBILE, "tools/screen-snapshots.mjs");
const TEST = "tests/quet-man-sau-tap.test.mjs";

/**
 * Every mutation names the file, an anchor that must appear EXACTLY once, its
 * replacement, and a fragment of the failure it should cause.
 *
 * The once-only rule is not politeness. An anchor that appears twice gets
 * patched in the copy the mutation did not mean, the run goes red for a real
 * but unintended reason, and the gate is credited with catching something it
 * never looked at.
 */
const DOT_BIEN = [
  {
    ten: "M1 · bỏ màn cuối khỏi danh sách quét",
    file: SCAN,
    neo: `  {
    step: "chia-se",`,
    thay: `  {
    step: "chia-se-DOT-BIEN",`,
    mongDoi: 'màn "chia-se" nằm trên đường đi nhưng không được quét',
  },
  {
    ten: "M2 · vừa quét vừa liệt là chưa quét",
    file: SCAN,
    neo: "export const CHUA_QUET = {};",
    thay: `export const CHUA_QUET = { "dot-thu": "Lý do dài hơn hai mươi ký tự để qua ca kiểm lý do." };`,
    mongDoi: 'màn "dot-thu" vừa nằm trong MAN_SAU_TAP vừa nằm trong CHUA_QUET',
  },
  {
    // Isolated on purpose: the excused screen is one STEPS does not contain, so
    // ca 1, 2 và 4 đều xanh và chỉ ca "lý do đọc được" có thể đỏ. Bản đầu của
    // M3 xoá luôn dòng quét dot-thu, nên nó đỏ ở ca 1 — cùng đường với M1, và
    // ca lý-do chưa từng được thử lần nào.
    ten: "M3 · tha bổng một màn bằng lý do cụt",
    file: SCAN,
    neo: "export const CHUA_QUET = {};",
    thay: `export const CHUA_QUET = { "man-la": "x" };`,
    mongDoi: 'màn "man-la" bị liệt là chưa quét nhưng lý do chỉ có "x"',
  },
  {
    ten: "M4 · quét một màn không có trên đường đi",
    file: SCAN,
    neo: `  { step: "nhap", needle: "Khoản chi mới", kichBan: DEN_NHAP },`,
    thay: `  { step: "nhap", needle: "Khoản chi mới", kichBan: DEN_NHAP },
  { step: "man-khong-co-that", needle: "x", kichBan: [] },`,
    mongDoi: 'MAN_SAU_TAP quét "man-khong-co-that" nhưng STEPS không có màn đó',
  },
  {
    ten: "M5 · thêm một màn vào đường đi mà không ai quét",
    file: WALK,
    neo: `  "chia-se",
];`,
    thay: `  "chia-se",
  "man-moi-chua-ai-do",
];`,
    mongDoi: 'màn "man-moi-chua-ai-do" nằm trên đường đi nhưng không được quét',
  },
  {
    ten: "M6 · đổi tên khối STEPS (cổng phải tố, không được im)",
    file: WALK,
    neo: "export const STEPS = [",
    thay: "export const STEPS_DOI_TEN = [",
    mongDoi: "không tìm thấy khai báo STEPS",
  },
];

function chay() {
  const r = spawnSync("node", ["--test", TEST], { cwd: MOBILE, encoding: "utf8" });
  return { ma: r.status, ra: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}

function khoiPhuc() {
  // Safe only because the baseline is COMMITTED. Run against a dirty tree this
  // would delete the very fix being measured -- that has happened here before.
  execFileSync("git", ["checkout", "--", SCAN, WALK], { cwd: MOBILE });
}

const sach = chay();
console.log(`nen sach: ma=${sach.ma} (can 0)`);
if (sach.ma !== 0) {
  console.log(sach.ra.slice(-1500));
  throw new Error("nen sach da do san -- moi con so duoi deu vo nghia");
}

let bat = 0;
for (const m of DOT_BIEN) {
  const goc = fs.readFileSync(m.file, "utf8");
  const soLan = goc.split(m.neo).length - 1;
  if (soLan !== 1) {
    // Not a warning. An anchor that is missing or doubled means this mutation
    // did not test what its name claims, so the run has no result to report.
    khoiPhuc();
    throw new Error(`${m.ten}: neo xuat hien ${soLan} lan trong ${path.basename(m.file)}, can dung 1`);
  }
  fs.writeFileSync(m.file, goc.replace(m.neo, m.thay));
  const sau = fs.readFileSync(m.file, "utf8");
  if (sau === goc) {
    khoiPhuc();
    throw new Error(`${m.ten}: ghi xong ma noi dung khong doi`);
  }

  const r = chay();
  const dungLyDo = r.ra.includes(m.mongDoi);
  const ket = r.ma === 0 ? "XANH (CONG MU)" : dungLyDo ? "DO dung ly do" : "DO NHAM LY DO";
  if (r.ma !== 0 && dungLyDo) bat++;
  console.log(`${m.ten}\n    -> ${ket}  (ma=${r.ma})`);
  if (r.ma !== 0 && !dungLyDo) {
    console.log(`    mong doi: ${m.mongDoi}`);
    const dong = r.ra.split("\n").filter((l) => /error:|AssertionError|màn |MAN_SAU_TAP|STEPS/.test(l));
    console.log(dong.slice(0, 6).map((l) => `    got: ${l.trim().slice(0, 140)}`).join("\n"));
  }
  khoiPhuc();
}

const lai = chay();
console.log(`\nsau khi khoi phuc: ma=${lai.ma} (can 0)`);
console.log(`bat dung ly do: ${bat}/${DOT_BIEN.length}`);
process.exitCode = bat === DOT_BIEN.length && lai.ma === 0 ? 0 : 1;
