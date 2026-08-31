/** Prove `tools/do-tran-chu.mjs` measures truncation, not merely box overflow.
 *
 *     cd apps/mobile && npm run build:check && node tools/dot-bien-tran-chu.mjs
 *
 * That file is its own gate: it carries a six-row canary page and aborts if any
 * row comes back wrong. So the question this table asks is the one that matters
 * about any self-gating measurement -- can the canary actually tell a broken
 * classifier from a working one, or does it only prove the tool still runs?
 *
 * The history says the question is not rhetorical. The classifier shipped as
 * `scrollWidth > clientWidth`, which is a different question from "is the text
 * cut off", and the four-row canary it shipped with could not tell the two
 * apart. On `ket-qua` that produced 15 false alarms against 2 real findings --
 * every one of them a delete button that deliberately bleeds into the Card
 * padding and is fully painted and hit-testable there.
 *
 * Two rows of this table were found by running it, not by reasoning:
 *
 *   - D was GREEN until the left-cut canary was rebuilt to cut on the LEFT
 *     ONLY. The first version overflowed both edges, so a right-edge-only
 *     measurement still found it, the count still came to 1, and the row printed
 *     `ok` while gating nothing.
 *   - C was GREEN until a canary row was added at the SIZE of a real defect.
 *     The two big rows cut 325 and 220 while the real `goi-y` truncation cuts
 *     12, so any threshold between them killed the real finding silently.
 *
 * ## The row that stays green on purpose
 *
 * F deletes the canary's own magnitude assertion and nothing notices. That is
 * inherent -- no gate gates its own assertions -- and it is listed rather than
 * omitted so that a reader of this table does not read "everything red" as
 * "everything covered". It is the one hole known to be open.
 *
 * Restores from a copy held in this process, never from git: the file under
 * mutation is usually newer than HEAD, and `git checkout --` would throw away
 * the very fix being tested. That is not hypothetical either -- it ate the
 * left-cut canary once during this file's own development.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { findChrome } from "../tests/chrome-cdp.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.join(HERE, "..");
const NGUON = path.join(MOBILE_ROOT, "tools/do-tran-chu.mjs");

const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ?? process.env.CHROME_BIN ?? findChrome() ?? "/usr/bin/google-chrome";

/* Two widths, not five. Every row below is decided on the canary page, which is
 * rendered once at the first width; the hero sweep is kept at 320 and 360 so the
 * `DA_BIET` ratchet still has both of its live entries to check, and so a
 * mutation that somehow passed the canary and broke a real reading would still
 * have somewhere to show up. Five widths would multiply the runtime by 2.5 and
 * add no row. */
const BE_NGANG = process.env.TRAN_BE_NGANG ?? "320,360";

/** @type {{ten:string, tim:string, thay:string, mong:"DO"|"XANH", vi:string, lo?:boolean}[]} */
const BANG = [
  {
    ten: "A: quay về luật tràn-hộp (chính là lỗi vừa sửa)",
    tim: "      cat = Math.max(cat, r.right - hop.phai, hop.trai - r.left);",
    thay: "      cat = Math.max(cat, el.scrollWidth - el.clientWidth);",
    mong: "DO",
    vi: "chữ vẽ ra ngoài hộp mà không hộp nào cắt thì không phải lỗi",
  },
  {
    ten: "B: không bao giờ tìm thấy hộp cắt (luôn lấy viewport)",
    tim: '      if (getComputedStyle(n).overflowX !== "visible") {',
    thay: "      if (false) {",
    mong: "DO",
    vi: "một tổ tiên overflow:hidden phải cắt được chữ nằm trong nó",
  },
  {
    ten: "C: nới ngưỡng 0.5 -> 25 (giết lỗi thật, giữ canary lớn)",
    tim: "    if (cat <= 0.5) continue;",
    thay: "    if (cat <= 25) continue;",
    mong: "DO",
    vi: "lỗi thật trên goi-y cắt 12pt; ngưỡng nào nuốt nó cũng phải đỏ",
  },
  {
    ten: "D: bỏ nửa phía trái của phép đo",
    tim: "      cat = Math.max(cat, r.right - hop.phai, hop.trai - r.left);",
    thay: "      cat = Math.max(cat, r.right - hop.phai);",
    mong: "DO",
    vi: "số canh phải trong hộp bị cắt mất chữ số ĐẦU, không mất chữ số cuối",
  },
  {
    ten: "E: bỏ bộ lọc cuộn-được",
    tim: "    if (cuonDuoc(el)) continue;",
    thay: "    if (false) continue;",
    mong: "DO",
    vi: "ma trận người trên goi-y cuộn ngang được, kéo tay là thấy, không phải lỗi",
  },
  {
    ten: "GIỮ TÍNH CHẤT: ngưỡng 0.5 -> 0.9 (vẫn dưới mọi lỗi thật)",
    tim: "    if (cat <= 0.5) continue;",
    thay: "    if (cat <= 0.9) continue;",
    mong: "XANH",
    vi: "chỗ cắt nhỏ nhất đo được là 10pt, nên 0.5 hay 0.9 chia y hệt nhau",
  },
  {
    ten: "GIỮ TÍNH CHẤT: đảo thứ tự hai vế trong Math.max",
    tim: "      cat = Math.max(cat, r.right - hop.phai, hop.trai - r.left);",
    thay: "      cat = Math.max(cat, hop.trai - r.left, r.right - hop.phai);",
    mong: "XANH",
    vi: "Math.max giao hoán: cùng một con số, mọi phán quyết giữ nguyên",
  },
  {
    ten: "F [LỖ ĐÃ BIẾT]: xoá chính phép kiểm độ lớn của canary",
    tim: "      const duCo = k.catToiDa === undefined || thay.every((t) => t.over <= k.catToiDa);",
    thay: "      const duCo = true;",
    mong: "XANH",
    lo: true,
    vi: "không cổng nào gác khẳng định của chính nó — ghi ra chứ không giấu",
  },
];

const goc = fs.readFileSync(NGUON, "utf8");

function chayDo() {
  try {
    execFileSync(process.execPath, [NGUON], {
      cwd: MOBILE_ROOT,
      env: { ...process.env, PUPPETEER_EXECUTABLE_PATH: CHROME, TRAN_BE_NGANG: BE_NGANG },
      stdio: "pipe",
    });
    return "XANH";
  } catch {
    return "DO";
  }
}

let hong = 0;
let loDaBiet = 0;
try {
  /* The clean tree must be green first. A table run against an already-red
   * measurement reports every row RED and reads like total coverage. */
  const nen = chayDo();
  console.log(`nen (chua dot bien, be ngang ${BE_NGANG}): ${nen}`);
  if (nen !== "XANH") {
    console.error("Cay sach da DO -- bang duoi se vo nghia. Sua truoc.");
    process.exit(1);
  }

  for (const m of BANG) {
    const so = goc.split(m.tim).length - 1;
    if (so !== 1) {
      /* An anchor that matches twice patches whichever copy comes first and
       * leaves the real one running, which prints GREEN and reads like a blind
       * spot that is not there. */
      console.error(`  ! neo "${m.ten}" khop ${so} lan (can dung 1) -- bo qua`);
      hong++;
      continue;
    }
    fs.writeFileSync(NGUON, goc.replace(m.tim, m.thay));
    const ket = chayDo();
    const dat = ket === m.mong;
    if (!dat) hong++;
    else if (m.lo) loDaBiet++;
    console.log(`${dat ? "OK  " : "SAI "} [${ket.padEnd(4)}] mong ${m.mong.padEnd(4)}  ${m.ten}`);
    console.log(`         vi: ${m.vi}`);
    fs.writeFileSync(NGUON, goc);
  }
} finally {
  fs.writeFileSync(NGUON, goc);
}

if (hong === 0) {
  console.log(
    `\nCA BANG DUNG NHU MONG DOI` +
      (loDaBiet ? ` -- trong do ${loDaBiet} hang la LO DA BIET con mo, khong phai da gac` : ""),
  );
} else {
  console.log(`\n${hong} hang KHONG nhu mong doi`);
}
process.exitCode = hong === 0 ? 0 : 1;
