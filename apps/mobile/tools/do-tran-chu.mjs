/** Which hero screens truncate text on the phone widths this product ships to?
 *
 * `quet-man-sau-tap.mjs` answers a different question than the one people read
 * it as answering. It runs the deterministic detector at ONE width, and the
 * detector's `text-overflow` rule has a threshold. Both facts are fine on their
 * own; together they produce a specific false clean, and this repo has already
 * shipped one:
 *
 *     "Gợi ý chia theo người" truncates to "Gợi ý chia theo ng…" at 360pt.
 *     The hero scanner run at 360x800 reports that screen `findings= 0 exit=0`.
 *
 * Both halves of that were measured, not reasoned about. The string needs 203pt
 * and gets 192pt at 360, so it really is clipped mid-word on the one screen
 * whose whole job is to say the AI read the bill; and the detector really does
 * return nothing for it, because 11px is under the rule's threshold. A reader
 * who trusts the scanner concludes the screen is fine at 360. It is not.
 *
 * So this file measures the geometry directly instead of asking a rule about
 * it. `scrollWidth > clientWidth` on an element with visible text is not a
 * matter of opinion or threshold, and it is reported in the raw at every width.
 *
 * ## Truncated is not the same as scrollable
 *
 * The naive version of this measurement is useless, and loudly so: the people
 * matrix on `goi-y` is a horizontal scroller, so it overflows its box by 265pt
 * at 414 and by 359pt at 320 -- by design, at every width, forever. Reporting
 * that as a defect would bury the 11pt one that matters under a permanent 300pt
 * one that does not.
 *
 * The discriminator is whether a person can still GET to the text:
 *
 *   - some ancestor scrolls on X (`overflow-x: auto|scroll`)  -> reachable, not
 *     a defect. The same call `che-chu.mjs` makes for occlusion findings that
 *     turn out to be scrolled-away rather than buried.
 *   - clipped (`overflow: hidden`, typically with `text-overflow: ellipsis`,
 *     which is what `numberOfLines={1}` compiles to under react-native-web)
 *     -> the characters cannot be revealed by any gesture. Defect.
 *
 * ## The positive control
 *
 * A file that reports "0 truncated" is worthless until something proves it can
 * report anything at all -- the failure this whole repo keeps re-learning. So a
 * canary page with one deliberately clipped heading and one deliberately
 * scrollable row is measured first, every run. It must come back with exactly
 * the clipped one. If it does not, the run aborts instead of printing zeros.
 *
 * ## The ratchet
 *
 * `DA_BIET` records truncations that are known, understood, and not fixable
 * inside a screen file. Each entry carries the measured overflow, so this is a
 * ratchet and not an exemption: a known 11pt that becomes 12pt goes red, and a
 * known one that reaches 0 goes red too, because a fixed defect left in this
 * list is how the list starts lying. Deleting an entry is the only way to
 * accept a fix.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/do-tran-chu.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, serverGiuNhip, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/**
 * The widths this measurement is claimed to cover, and why these five.
 *
 * 320 is the narrowest phone still in the support matrix, 360 is the single
 * most common Android width in Vietnam, 375 and 390 are the iPhone mini/standard
 * pair, and 414 is the large-phone class. The mockups are drawn at 390, which is
 * exactly why 390 alone is not a measurement: it is the one width the design was
 * fitted to and therefore the least likely to fail.
 */
const BE_NGANG = (process.env.TRAN_BE_NGANG ?? "320,360,375,390,414").split(",").map((s) => Number(s.trim()));
const CAO = Number(process.env.TRAN_CAO ?? 844);

/**
 * Truncations already understood, with the number that was measured.
 *
 * Not an exemption list. Each entry is a claim that can go stale, and the `over`
 * value is what makes it falsifiable -- see the ratchet note in the file header.
 */
const DA_BIET = [
  {
    step: "goi-y",
    rong: 360,
    chu: "Gợi ý chia theo người",
    over: 11,
    ly:
      "Hàng tiêu đề còn chevron 44 (tap target) + 'Món của tôi' 72 (nút đường hero). " +
      "Đóng nốt 11pt cần một bậc chữ theo bề ngang, tức quyết định về thang trong " +
      "DESIGN.md, không phải sửa trong một file màn. Đã báo Lead, chưa có phán quyết.",
  },
  {
    step: "goi-y",
    rong: 320,
    chu: "Gợi ý chia theo người",
    over: 51,
    ly: "Cùng nguyên nhân với ca 360, xa hơn 40pt. Cùng một bản sửa sẽ đóng cả hai.",
  },
];

/** One deliberately clipped heading and one deliberately scrollable row. The
 *  measurement below must return the first and not the second; a run that
 *  cannot tell them apart cannot be trusted about any real screen. */
const CANARY = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>canary tran chu</title><style>
 body { margin:0; font: 16px/1.4 system-ui, sans-serif; color:#1a1a1a; background:#fff; }
 .clip { width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
 .scroll { width:120px; overflow-x:auto; white-space:nowrap; }
</style></head><body>
 <div class="clip">CANARY BI CAT MOT CHUOI RAT DAI KHONG THE HIEN HET</div>
 <div class="scroll">CANARY CUON DUOC MOT CHUOI RAT DAI NHUNG KEO NGANG DUOC</div>
</body></html>`;

/**
 * Every element whose own text is wider than the box it was given AND which no
 * ancestor can scroll into view.
 *
 * Runs inside the page. Innermost wins: a clipped leaf also makes each of its
 * ancestors measure over, and reporting the chain would turn one defect into
 * five lines naming the same characters.
 */
function doTrongTrang() {
  const cuonDuoc = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === "auto" || ox === "scroll") return true;
    }
    return false;
  };
  const els = [];
  for (const el of document.querySelectorAll("*")) {
    const over = el.scrollWidth - el.clientWidth;
    if (over <= 0 || el.clientWidth <= 0) continue;
    const chu = (el.innerText ?? "").trim().replace(/\s+/g, " ");
    if (!chu) continue;
    if (cuonDuoc(el)) continue;
    els.push(el);
  }
  /* Innermost wins, by DOM containment rather than by comparing the strings.
   * The string version silently kept whole chains: a row whose only text is a
   * "×" button has the SAME innerText as the six nested boxes under it, and
   * `a.chu !== b.chu` dropped every one of those comparisons, so one 10pt
   * overflow printed six identical lines. Containment has no such tie. */
  return els
    .filter((a) => !els.some((b) => b !== a && a.contains(b)))
    .map((el) => ({
      chu: (el.innerText ?? "").trim().replace(/\s+/g, " ").slice(0, 60),
      over: el.scrollWidth - el.clientWidth,
      sw: el.scrollWidth,
      cw: el.clientWidth,
      // What it is, not just what it says: "×" names six different boxes, and a
      // fix needs to know which one was measured.
      nut: `${el.tagName.toLowerCase()}${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""}`,
    }));
}

/** Load one page at one width and return what it truncates. */
async function doMotMan(browser, url, needle, rong) {
  const page = await browser.newPage();
  try {
    page.setDefaultTimeout(60000);
    await page.setViewport({ width: rong, height: CAO, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await page.goto(url, { waitUntil: "networkidle0" });
    if (needle) {
      /* Same anchor the hero scanner uses. Without it a screen that never
       * finished its walk still measures cleanly -- as the opening screen,
       * under this screen's name. */
      await page
        .waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), { timeout: 60000 })
        .catch(() => {});
      const co = await page.evaluate((n) => (document.body.innerText || "").includes(n), needle);
      if (!co) return { toiDuoc: false, tran: [] };
    }
    return { toiDuoc: true, tran: await page.evaluate(doTrongTrang) };
  } finally {
    await page.close();
  }
}

async function main() {
  const buildDir = path.join(MOBILE_ROOT, ".expo-build-check");
  const indexPath = path.join(buildDir, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error(`khong co ${indexPath} -- chay "npm run build:check" truoc`);
  }
  const indexHtml = fs.readFileSync(indexPath, "utf8");

  const viet = [];
  const ghi = (ten, noiDung) => {
    const p = path.join(buildDir, ten);
    fs.writeFileSync(p, noiDung);
    viet.push(p);
    return ten;
  };

  const tenCanary = ghi("__tran-canary.html", CANARY);
  for (const { step, kichBan } of MAN_SAU_TAP) {
    ghi(`__tran-${step}.html`, trangTuLai(indexHtml, kichBan));
  }

  const server = serverGiuNhip(buildDir);
  let browser = null;
  let xau = 0;
  let khongToiDuoc = 0;
  try {
    const goc = `http://127.0.0.1:${await listen(server)}`;
    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    console.log(`== doi chung: trang canary (${BE_NGANG[0]}pt) ==`);
    const cn = await doMotMan(browser, `${goc}/${tenCanary}`, null, BE_NGANG[0]);
    const batDuoc = cn.tran.filter((t) => t.chu.startsWith("CANARY BI CAT"));
    const batNham = cn.tran.filter((t) => t.chu.startsWith("CANARY CUON DUOC"));
    console.log(`  bi cat  : ${batDuoc.length} (can = 1)   ${batDuoc.map((t) => `over ${t.over}`).join("")}`);
    console.log(`  cuon duoc: ${batNham.length} (can = 0)`);
    if (batDuoc.length !== 1) {
      throw new Error(
        "PHEP DO DA MU: chuoi bi cat co tinh khong duoc bao. Moi so 0 duoi day la vo nghia.",
      );
    }
    if (batNham.length !== 0) {
      throw new Error(
        "PHEP DO BAT NHAM: mot hang cuon ngang duoc bi bao la cat. Bang duoi se chim " +
          "trong bao dong gia va cai 11pt that se khong ai thay.",
      );
    }

    console.log(`\n== ${MAN_SAU_TAP.length} man hero x ${BE_NGANG.length} be ngang ==`);
    const bangKe = [];
    for (const { step, needle } of MAN_SAU_TAP) {
      for (const rong of BE_NGANG) {
        const kq = await doMotMan(browser, `${goc}/__tran-${step}.html`, needle, rong);
        if (!kq.toiDuoc) {
          khongToiDuoc += 1;
          console.log(`  ${step.padEnd(18)} ${String(rong).padStart(3)}pt  CHUA KET LUAN DUOC (khong toi duoc man)`);
          continue;
        }
        for (const t of kq.tran) {
          const biet = DA_BIET.find((d) => d.step === step && d.rong === rong && d.chu === t.chu);
          const trangThai = !biet ? "MOI" : biet.over === t.over ? "da biet" : `DOI (ghi ${biet.over})`;
          if (trangThai !== "da biet") xau += 1;
          bangKe.push({ step, rong, ...t, trangThai });
          console.log(
            `  ${step.padEnd(18)} ${String(rong).padStart(3)}pt  over ${String(t.over).padStart(3)}` +
              `  ${t.sw}/${t.cw}  ${t.nut}  "${t.chu}"  [${trangThai}]`,
          );
        }
      }
    }

    /* A `DA_BIET` entry that never matched is the other direction of the same
     * lie: the defect was fixed (or the string changed) and the list still
     * claims it is outstanding, so the next reader budgets for work that is
     * already done. */
    for (const d of DA_BIET) {
      const thay = bangKe.some((b) => b.step === d.step && b.rong === d.rong && b.chu === d.chu);
      if (!thay) {
        xau += 1;
        console.log(
          `  DA_BIET THUA: ${d.step} @${d.rong}pt "${d.chu}" khong con tran nua. ` +
            `Xoa dong do khoi DA_BIET -- giu lai la khai bao mot lo hong khong ton tai.`,
        );
      }
    }

    const moi = bangKe.filter((b) => b.trangThai !== "da biet");
    console.log(`\ntong: ${bangKe.length} cho tran, ${moi.length} chua duoc chap nhan`);
    const outDir = path.join(MOBILE_ROOT, ".tab-scan");
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(
      path.join(outDir, "tran-chu.json"),
      JSON.stringify({ beNgang: BE_NGANG, cao: CAO, canary: { batDuoc: batDuoc.length, batNham: batNham.length }, tran: bangKe, daBiet: DA_BIET }, null, 2),
    );
    console.log(`chi tiet: ${path.join(outDir, "tran-chu.json")}`);
  } finally {
    if (browser) await browser.close();
    for (const res of server.__treo) res.destroy();
    await closeServer(server);
    for (const p of viet) {
      try {
        fs.unlinkSync(p);
      } catch (err) {
        if (err.code !== "ENOENT") throw err;
      }
    }
  }

  /* Three states, same shape as the hero scanner: 0 clean, 2 a truncation that
   * nobody has accepted, 4 nothing broken but at least one screen could not be
   * reached so its silence means nothing. */
  process.exitCode = xau > 0 ? 2 : khongToiDuoc > 0 ? 4 : 0;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
