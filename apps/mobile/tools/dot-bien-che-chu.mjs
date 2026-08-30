/** Prove `tests/che-chu.test.mjs` measures the property, not the file's mtime.
 *
 *     node tools/dot-bien-che-chu.mjs
 *
 * The filter this gate guards turns four warnings green. That is exactly the
 * shape of change that has to be shown to still fail when it should, because
 * the cheapest way to make a scan clean is to build a filter that clears
 * everything -- and a filter that clears everything passes any test that only
 * checks "artifacts are not reported".
 *
 * So the table has both directions, and a negative control:
 *
 *   - three rows BREAK the property and must turn the gate RED
 *   - two rows PRESERVE the property while still editing the file, and must
 *     leave it GREEN
 *
 * The negative controls are the half that carries the information. Three red
 * rows only show the gate reacts to *some* edit; they cannot tell "measures
 * the property" apart from "notices somebody touched the file". A gate that
 * goes red at everything is as useless as one that never does, and costs more
 * to discover.
 *
 * Restores from a copy held in this process, never from git: the file under
 * mutation is often newer than HEAD, and `git checkout --` would throw away
 * the very fix being tested.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.join(HERE, "..");
const NGUON = path.join(MOBILE_ROOT, "tools/che-chu.mjs");
const GATE = path.join(MOBILE_ROOT, "tests/che-chu.test.mjs");

const CHROME =
  process.env.CHROME_BIN ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

/** @type {{ten:string, tim:string, thay:string, mong:"DO"|"XANH", vi:string}[]} */
const BANG = [
  {
    ten: "luôn trả 'cuon-khuat' (bộ lọc xoá sạch mọi cảnh báo)",
    tim: 'verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "to-cha" : "that",',
    thay: 'verdict: "cuon-khuat",',
    mong: "DO",
    vi: "chữ bị hộp đục đè lên vẫn phải là lỗi",
  },
  {
    ten: "luôn trả 'that' (mọi ảo ảnh thành lỗi)",
    tim: 'verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "to-cha" : "that",',
    thay: 'verdict: "that",',
    mong: "DO",
    vi: "chữ chỉ cuộn khuất thì không được tính là lỗi",
  },
  {
    ten: "'that' lọt vào danh sách loại trừ",
    tim: 'const DA_LOAI_TRU = new Set(["cuon-khuat", "to-cha"]);',
    thay: 'const DA_LOAI_TRU = new Set(["cuon-khuat", "to-cha", "that"]);',
    mong: "DO",
    vi: "laLoiThat phải còn đúng với lỗi thật",
  },
  {
    ten: "GIỮ TÍNH CHẤT: dời điểm mẫu, vẫn cắt ngang giữa dòng chữ",
    tim: "const diem = [0.1, 0.3, 0.5, 0.7, 0.9].map((f) => ({ x: r.left + r.width * f, y }));",
    thay: "const diem = [0.2, 0.4, 0.5, 0.6, 0.8].map((f) => ({ x: r.left + r.width * f, y }));",
    mong: "XANH",
    vi: "vẫn lấy mẫu dọc giữa chữ, nên mọi verdict giữ nguyên",
  },
  {
    ten: "GIỮ TÍNH CHẤT: hạ ngưỡng 0.6 -> 0.55",
    tim: "verdict: tyLe >= 0.6 ?",
    thay: "verdict: tyLe >= 0.55 ?",
    mong: "XANH",
    vi: "kết quả thật là 5/5 hoặc 0/5, ngưỡng nào giữa 0 và 1 cũng chia y hệt",
  },
];

const goc = fs.readFileSync(NGUON, "utf8");

function chayGate() {
  try {
    execFileSync(process.execPath, ["--test", GATE], {
      cwd: MOBILE_ROOT,
      env: { ...process.env, CHROME_BIN: CHROME, MOBILE_REQUIRE_CHE_CHU: "1" },
      stdio: "pipe",
    });
    return "XANH";
  } catch {
    return "DO";
  }
}

let hong = 0;
try {
  // The clean tree must be green first. A table run against an already-red
  // gate reports every row as RED and reads like total coverage.
  const nen = chayGate();
  console.log(`nen (chua dot bien): ${nen}`);
  if (nen !== "XANH") {
    console.error("Cay sach da DO -- bang duoi se vo nghia. Sua truoc.");
    process.exit(1);
  }

  for (const m of BANG) {
    const so = goc.split(m.tim).length - 1;
    if (so !== 1) {
      // Anchoring on a string that appears twice patches whichever copy comes
      // first and leaves the real one running, which prints GREEN and reads
      // like a blind spot that is not there.
      console.error(`  ! neo "${m.ten}" khop ${so} lan (can dung 1) -- bo qua`);
      hong++;
      continue;
    }
    fs.writeFileSync(NGUON, goc.replace(m.tim, m.thay));
    const thay = fs.readFileSync(NGUON, "utf8");
    if (thay === goc) {
      console.error(`  ! "${m.ten}" khong doi duoc file`);
      hong++;
      continue;
    }
    const ket = chayGate();
    const dat = ket === m.mong;
    if (!dat) hong++;
    console.log(`${dat ? "OK  " : "SAI "} [${ket.padEnd(4)}] mong ${m.mong.padEnd(4)}  ${m.ten}`);
    console.log(`         vi: ${m.vi}`);
    fs.writeFileSync(NGUON, goc);
  }
} finally {
  fs.writeFileSync(NGUON, goc);
}

console.log(hong === 0 ? "\nCA BANG DUNG NHU MONG DOI" : `\n${hong} hang KHONG nhu mong doi`);
process.exitCode = hong === 0 ? 0 : 1;
