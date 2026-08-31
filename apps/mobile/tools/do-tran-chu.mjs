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
 * it: how much of each run of text is painted outside the nearest box that
 * clips it, reported in the raw at every width.
 *
 * ## Truncated is not the same as scrollable, and not the same as overflowing
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
 *   - nothing clips it, it is merely painted outside its own box (`overflow:
 *     visible`, the default) -> visible, not a defect. This is the one the
 *     first version of this file got wrong; the delete button on `ket-qua`
 *     bleeds 10pt into the Card padding on purpose and produced 15 of the 17
 *     lines in the table, against 2 real ones.
 *   - clipped (`overflow: hidden`, typically with `text-overflow: ellipsis`,
 *     which is what `numberOfLines={1}` compiles to under react-native-web)
 *     -> the characters cannot be revealed by any gesture. Defect.
 *
 * ## The positive control
 *
 * A file that reports "0 truncated" is worthless until something proves it can
 * report anything at all -- the failure this whole repo keeps re-learning. So a
 * canary page is measured first, every run, and the run aborts instead of
 * printing zeros if any row comes back wrong. Two of its six rows must stay
 * SILENT: a control table that only proves a tool can shout does not prove it
 * can tell the difference, and telling the difference is this file's whole job.
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
    over: 12,
    ly:
      "Hàng tiêu đề còn chevron 44 (tap target) + 'Món của tôi' 72 (nút đường hero). " +
      "Đóng nốt cần một bậc chữ theo bề ngang, tức quyết định về thang trong " +
      "DESIGN.md, không phải sửa trong một file màn. Đã báo Lead, chưa có phán quyết. " +
      "Con số là 12 chứ không phải 11 như bản ghi cũ, và MÀN KHÔNG XẤU ĐI: 11 là " +
      "`scrollWidth - clientWidth` của cái hộp, 12 là phần chữ thật sự vẽ ra ngoài " +
      "mép hộp cắt nó. Chữ bắt đầu lệch vào 1pt so với mép trong của hộp, nên số đo " +
      "mới lớn hơn đúng 1. Đo cái người đọc mất, không đo cái hộp thừa.",
  },
  {
    step: "goi-y",
    rong: 320,
    chu: "Gợi ý chia theo người",
    over: 52,
    ly: "Cùng nguyên nhân với ca 360, xa hơn 40pt. Cùng một bản sửa sẽ đóng cả hai.",
  },
];

/**
 * Six rows, and the two that must stay SILENT are as load-bearing as the four
 * that must come back red.
 *
 * `bi-cat` and `cuon-duoc` are the original pair: one clipped, one scrollable.
 * Each of the other four was added because a mutation of the measurement below
 * survived without it -- the letter is the row in the mutation table it kills:
 *
 *   `ra-le` (A) renders text outside its own box with every ancestor `overflow:
 *   visible` -- painted, readable, hit-testable. `scrollWidth > clientWidth` is
 *   TRUE for it, so a box-overflow rule calls it truncated. It is not.
 *   `to-cha-cat` (B) is the same shape with one grandparent set to `overflow:
 *   hidden`, so the characters really do stop existing at the same geometry.
 *   `cat-it` (C) is cut by ~10pt, the size of a real defect on this app, and
 *   asserts the magnitude as well as the count: the two big rows cut 325 and
 *   220, so a threshold slipped in between them would kill the 12pt truncation
 *   on `goi-y` and still print "ok" twice.
 *   `cat-ben-trai` (D) loses the HEAD of its string, which is what a
 *   right-aligned amount does inside a clipped box. Without it, deleting half
 *   the measurement passes.
 *
 * Any classifier that gets `ra-le` right by being more permissive gets
 * `to-cha-cat` wrong, and a run that reports both or neither has stopped
 * measuring the thing it is named after.
 */
const CANARY = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>canary tran chu</title><style>
 body { margin:0; font: 16px/1.4 system-ui, sans-serif; color:#1a1a1a; background:#fff; }
 .clip { width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
 .scroll { width:120px; overflow-x:auto; white-space:nowrap; }
 .bleed-outer { width:120px; }
 .bleed-inner { width:60px; white-space:nowrap; }
 .hide-outer { width:120px; overflow:hidden; }
 /* 22 ky tu trong 21ch: cat ra dung mot ch, co cua mot loi that. */
 .it { font-family:monospace; width:21ch; overflow:hidden; white-space:nowrap; }
 /* Cat o phia TRAI. Dat bang toa do tuyet doi chu khong bang text-align/rtl:
  * hai cach kia con phu thuoc bidi, con cai nay thi hinh hoc noi thang. */
 .trai-outer { width:120px; overflow:hidden; position:relative; height:1.4em; }
 .trai-inner { position:absolute; left:-40px; white-space:nowrap; }
</style></head><body>
 <div class="clip">CANARY BI CAT MOT CHUOI RAT DAI KHONG THE HIEN HET</div>
 <div class="scroll">CANARY CUON DUOC MOT CHUOI RAT DAI NHUNG KEO NGANG DUOC</div>
 <div class="bleed-outer"><div class="bleed-inner">CANARY RA LE VAN DOC DUOC</div></div>
 <div class="hide-outer"><div class="bleed-inner">CANARY TO CHA CAT KHONG DOC HET DUOC</div></div>
 <div class="it">CANARY CAT IT MOT CHU!</div>
 <div class="trai-outer"><div class="trai-inner">CANARY CAT BEN TRAI MAT DAU</div></div>
</body></html>`;

/**
 * Every run of text whose painted width is cut off by a box it cannot escape.
 *
 * Runs inside the page. The unit is a TEXT NODE, not an element, and that is
 * the correction this function carries. The old version asked each element
 * `scrollWidth > clientWidth` and called a positive answer truncation unless
 * some ancestor scrolled. Those are not the same question, and CSS is why: with
 * the default `overflow: visible`, content that does not fit its box is still
 * PAINTED outside it. The box overflows; the reader loses nothing.
 *
 * Measured cost of the difference, on `ket-qua` at five widths: 15 lines, every
 * one of them the delete button of a dish row. That button carries a deliberate
 * `marginRight: -space.sm` so its 44pt tap target overhangs the row track into
 * the Card's padding, and the render agrees it is fine -- at 390pt the button
 * sits at [329,373] inside a clipping ancestor that ends at 374, and
 * `elementFromPoint` at its rightmost painted column returns the button itself.
 * The one real defect in the same table, an 11pt clip on `goi-y`, printed
 * fifteenth. A measurement whose false alarms outnumber its findings 15:2 gets
 * read as noise, which is the same outcome as not running it.
 *
 * So: find each text run's painted rectangle, find the nearest ancestor that
 * actually clips (`overflow-x` not `visible`), and report the overhang between
 * them. `overflow: hidden` on the element itself is the ordinary case -- that is
 * what `numberOfLines={1}` compiles to under react-native-web -- and it is
 * caught by the same rule with no special case, because such an element is its
 * own nearest clipper.
 *
 * Horizontal only, deliberately: the question is which phone widths truncate,
 * and vertical clipping on a scrolling screen is a different defect with a
 * different fix.
 */
function doTrongTrang() {
  /* Reachable by dragging is not truncated -- the horizontal people-matrix on
   * `goi-y` overflows by 265pt at 414 by design, forever. */
  const cuonDuoc = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === "auto" || ox === "scroll") return true;
    }
    return false;
  };
  /* The first box on the way up that would actually cut paint. `visible` boxes
   * are skipped however small they are; that is the whole point. Nothing above
   * the viewport can clip, so the viewport is the backstop. */
  const hopCat = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      if (getComputedStyle(n).overflowX !== "visible") {
        const r = n.getBoundingClientRect();
        const cs = getComputedStyle(n);
        // Content box: padding still shows paint, borders do not.
        return {
          trai: r.left + parseFloat(cs.borderLeftWidth || "0"),
          phai: r.right - parseFloat(cs.borderRightWidth || "0"),
          ten: `${n.tagName.toLowerCase()}${n.getAttribute("role") ? `[role=${n.getAttribute("role")}]` : ""}`,
        };
      }
    }
    return { trai: 0, phai: window.innerWidth, ten: "viewport" };
  };

  const ra = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const chu = (node.nodeValue ?? "").trim().replace(/\s+/g, " ");
    if (!chu) continue;
    const el = node.parentElement;
    if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
    if (cuonDuoc(el)) continue;

    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
    range.detach?.();
    if (!rects.length) continue;

    const hop = hopCat(el);
    /* Right and left separately: a right-aligned label in a clipped box loses
     * its head, not its tail, and reporting only one side would call that
     * clean. */
    let cat = 0;
    for (const r of rects) {
      cat = Math.max(cat, r.right - hop.phai, hop.trai - r.left);
    }
    if (cat <= 0.5) continue;

    const rong = Math.max(...rects.map((r) => r.right)) - Math.min(...rects.map((r) => r.left));
    ra.push({
      chu: chu.slice(0, 60),
      over: Math.round(cat),
      sw: Math.round(rong),
      cw: Math.round(hop.phai - hop.trai),
      // What cut it, not just what it says: on this app "×" names six boxes and
      // a fix needs to know which one was measured.
      nut: `${el.tagName.toLowerCase()}${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""} trong ${hop.ten}`,
    });
  }
  return ra;
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
    /* Two rows must come back and two must stay silent. Both halves are the
     * control: a classifier tuned until the false alarms go away also stops
     * reporting the real thing, and only the `can = 1` rows can tell. */
    const CHO_DOI = [
      { ma: "CANARY BI CAT", can: 1, ly: "chuoi bi chinh hop cua no cat" },
      { ma: "CANARY CUON DUOC", can: 0, ly: "hang cuon ngang duoc, keo tay la thay" },
      { ma: "CANARY RA LE", can: 0, ly: "chu ve ngoai hop nhung khong hop nao cat -- van doc duoc" },
      { ma: "CANARY TO CHA CAT", can: 1, ly: "cung hinh dang, nhung mot to cha overflow:hidden" },
      /* Hai hang `can = 1` kia cat 325 va 220. Loi that tren `goi-y` cat 12.
       * Mot nguong lot vao giua se giet cai 12 va van in "ok" hai lan, nen phai
       * co mot hang doi chung dung CO cua loi that. */
      { ma: "CANARY CAT IT", can: 1, catToiDa: 25, ly: "cat nho co mot ky tu -- co cua loi that tren may" },
      /* Chi hang nay bat duoc viec bo nua phia trai cua phep do. Khong co no,
       * xoa `hop.trai - r.left` van in "ok" ca bang -- da do bang dot bien D. */
      { ma: "CANARY CAT BEN TRAI", can: 1, ly: "cat mat DAU chuoi: nhan canh phai trong hop bi cat" },
    ];
    let canarySai = 0;
    for (const k of CHO_DOI) {
      const thay = cn.tran.filter((t) => t.chu.startsWith(k.ma));
      const duCo = k.catToiDa === undefined || thay.every((t) => t.over <= k.catToiDa);
      const dat = thay.length === k.can && duCo;
      if (!dat) canarySai += 1;
      console.log(
        `  ${dat ? "ok  " : "SAI "} ${k.ma.padEnd(18)} thay ${thay.length} (can = ${k.can})` +
          `${thay.length ? `  cat ${thay.map((t) => t.over).join(",")}` : ""}` +
          `${k.catToiDa !== undefined ? ` (can <= ${k.catToiDa})` : ""}   ${k.ly}`,
      );
    }
    if (canarySai > 0) {
      throw new Error(
        `PHEP DO KHONG PHAN BIET DUOC: ${canarySai}/4 hang doi chung sai. Moi con so duoi day ` +
          "la vo nghia -- ca so 0 lan so khac 0.",
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
      JSON.stringify(
        {
          beNgang: BE_NGANG,
          cao: CAO,
          // The whole control table, not a pass/fail bit: a reader who wants to
          // know whether the zeros mean anything needs the `can = 1` rows too.
          canary: CHO_DOI.map((k) => ({
            ma: k.ma,
            can: k.can,
            thay: cn.tran.filter((t) => t.chu.startsWith(k.ma)).length,
          })),
          tran: bangKe,
          daBiet: DA_BIET,
        },
        null,
        2,
      ),
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
