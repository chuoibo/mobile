/** How much real burial does the filter erase? The behavioural half of #259.
 *
 *     cd apps/mobile && npm run build:check && node tools/probe-xoa-nham-that.mjs
 *
 * `probe-chung-lop.mjs` (#259) answers a question about SHAPE: on the rendered
 * screens, how many (occluder, text) pairs sit in the class-superset relation
 * the `to-cha` shortcut keys on. It walks the DOM and never loads
 * `che-chu.mjs`, so its 88.4% is a property of react-native-web's atomic
 * classes, not of the filter. Patching the filter cannot move that number.
 * Both ways of reading it afterwards are traps: re-running it, seeing 88.4%
 * unchanged and concluding the fix did nothing; or editing their probe until
 * it prints 0, which is sanding down the instrument that found the bug.
 *
 * This file asks the other half, the one a patch CAN move: of the burials that
 * actually happen, how many does the filter clear? For every text run on each
 * screen it
 *
 *   1. scrolls the words to the middle of the viewport,
 *   2. drops a real opaque overlay across them, carrying exactly the class
 *      list of one of their own ancestors -- the collision rnw produces when
 *      two elements are handed the same style props, and the reason the
 *      selector the detector prints for the overlay also matches an ancestor,
 *   3. runs the real `phanLoai` over the finding the detector would have
 *      written, and
 *   4. keeps the pair only if the burial actually took (0 sample points
 *      readable), then asks `laLoiThat` whether the warning survives.
 *
 * Denominator is burials that took, never attempts. An overlay that missed
 * would otherwise count as a text the filter "correctly" kept, which inflates
 * the score of a filter that erases everything.
 *
 * ## Why it classifies everything twice
 *
 * A "0% wrongly erased" from this probe is worth nothing on its own: a broken
 * overlay, a selector that stopped matching, or an exception swallowed
 * somewhere all print the same 0%. So every burial is also handed to a PINNED
 * PRE-PATCH copy of the filter, in the same page state, and the run REFUSES to
 * report unless that control comes back dirty. Same discipline as the ugly
 * canary in `quet-tab-url.mjs`: a clean number only means something once the
 * instrument has been shown to be awake on the same measurement.
 *
 * The control is pinned by commit, and the extracted source is checked for the
 * shortcut before it is trusted. Anchoring a control on a moving ref is how a
 * control quietly becomes a no-op that still prints its reassuring column.
 *
 * Three outcomes, never two:
 *   0  DAT               control dirty, filter under test erased nothing
 *   1  HONG              filter under test erased a real burial
 *   3  CHUA KET LUAN DUOC control unavailable or blind -- NOT a pass
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, installTabStubs, moiMan, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.join(HERE, "..");
const BUILD = path.join(MOBILE_ROOT, ".expo-build-check");

/** #255, the commit that introduced the shortcut. The control is this file's
 *  `che-chu.mjs`, and the substring below is the shortcut itself: if a future
 *  rewrite makes the extraction succeed while no longer containing it, the
 *  control would be measuring nothing and must fail loudly instead. */
const SHA_DOI_CHUNG = process.env.CHE_CHU_SHA_DOI_CHUNG ?? "c9532cf";
const DAU_DUONG_TAT = ': cha ? "to-cha" : "that"';

/** Texts measured per screen. Bounded so the run stays inside one turn; the
 *  number skipped by the cap is printed, never silently dropped. */
const TRAN_MOI_MAN = 12;

const CHUA_KET_LUAN = 3;

function thoiChuaKetLuan(vi) {
  console.error(`\nCHUA KET LUAN DUOC: ${vi}`);
  console.error("Khong phai DAT: khong biet phep do co chay that khong.");
  process.exit(CHUA_KET_LUAN);
}

const DUONG_CHINH = process.env.CHE_CHU_MODULE
  ? path.resolve(process.env.CHE_CHU_MODULE)
  : path.join(HERE, "che-chu.mjs");

/** Pull the pre-patch filter out of history into a temp file. */
function layDoiChung() {
  let nguon;
  try {
    nguon = execFileSync("git", ["show", `${SHA_DOI_CHUNG}:apps/mobile/tools/che-chu.mjs`], {
      cwd: MOBILE_ROOT,
      encoding: "utf8",
      maxBuffer: 8 << 20,
    });
  } catch (e) {
    thoiChuaKetLuan(`khong lay duoc che-chu.mjs tai ${SHA_DOI_CHUNG}: ${String(e.message).slice(0, 200)}`);
  }
  if (!nguon.includes(DAU_DUONG_TAT)) {
    thoiChuaKetLuan(
      `che-chu.mjs tai ${SHA_DOI_CHUNG} KHONG con chua duong tat to-cha ` +
        `(${DAU_DUONG_TAT}). Doi chung nay khong do gi ca -- ghim lai sha.`,
    );
  }
  const p = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "che-chu-doi-chung-")), "che-chu.mjs");
  fs.writeFileSync(p, nguon);
  return p;
}

const DUONG_DOI_CHUNG = layDoiChung();
const chinh = await import(pathToFileURL(DUONG_CHINH).href);
const doiChung = await import(pathToFileURL(DUONG_DOI_CHUNG).href);

const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
const fixtures = taoFixtures();
const tiem =
  `<script>(${installTabStubs.toString()})(` +
  `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
const i = indexHtml.indexOf("<head>");
const trang = indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6);

/** Text runs worth burying, with the ancestor whose classes the overlay wears.
 *
 * Serialized into the page. Only unique texts: `phanLoai` folds every element
 * whose text starts with the needle into one worst-verdict answer, so a label
 * that repeats would mix a buried copy with untouched ones. */
function timUngVien() {
  const la = (el) => el.children.length === 0 && (el.textContent ?? "").trim().length > 0;
  const hopLe = (c) => /^[A-Za-z_-][\w-]*$/.test(c);
  const all = [...document.querySelectorAll("div,span,p,h1,h2,h3,h4,li,a,button")];
  const la_ = all.filter(la);

  const dem = new Map();
  for (const el of la_) {
    const t = (el.textContent ?? "").trim();
    dem.set(t, (dem.get(t) ?? 0) + 1);
  }

  const ra = [];
  for (const el of la_) {
    const chu = (el.textContent ?? "").trim();
    if (dem.get(chu) !== 1) continue;
    if (chu.includes('"')) continue; // would break the snippet the detector writes
    if (chu.length < 3 || chu.length > 60) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;

    // Nearest ancestor carrying a usable class list. This is the element whose
    // class set the overlay copies, and therefore the selector the detector
    // would print for the overlay.
    let sel = null;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cn = String(p.className ?? "").trim();
      if (!cn) continue;
      const lop = cn.split(/\s+/).filter(hopLe);
      if (!lop.length) continue;
      sel = { tag: p.tagName.toLowerCase(), lop };
      break;
    }
    if (!sel) continue;
    ra.push({ chu, tag: sel.tag, lop: sel.lop, selector: `${sel.tag}.${sel.lop.join(".")}` });
  }
  return ra;
}

/** Bury one text run. Returns the rect covered, or null when the words could
 *  not be brought on-screen -- those are dropped, not counted as survivors. */
function chon(chu, tag, lop) {
  const la = (el) => el.children.length === 0 && (el.textContent ?? "").trim().length > 0;
  const el = [...document.querySelectorAll("div,span,p,h1,h2,h3,h4,li,a,button")].find(
    (e) => la(e) && (e.textContent ?? "").trim() === chu,
  );
  if (!el) return null;
  try {
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" });
  } catch {
    el.scrollIntoView(true);
  }
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  if (!(r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth)) return null;

  // `fixed`, pinned to where the words sit AFTER the same centring scroll
  // `phanLoai` performs. Survives inner scroll containers, which page-coordinate
  // maths would not. No `pointer-events:none`: that would hide the overlay from
  // `elementsFromPoint` and stage a burial that never happened.
  const ov = document.createElement(tag);
  ov.className = lop.join(" ");
  ov.setAttribute("data-probe-chon", "1");
  ov.style.cssText =
    `position:fixed;left:${r.left - 4}px;top:${r.top - 2}px;` +
    `width:${r.width + 8}px;height:${r.height + 4}px;` +
    // Kept short on purpose: the repo guard reads a long digit run as a
    // possible account number, and nothing on these screens stacks this high.
    "background:#123456;opacity:1;z-index:99999";
  document.body.appendChild(ov);
  return { w: Math.round(r.width), h: Math.round(r.height) };
}

function doChon() {
  for (const e of document.querySelectorAll("[data-probe-chon]")) e.remove();
}

const man = moiMan();
const server = createStaticServer(BUILD);
const viet = [];
let browser = null;
const bang = [];
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  for (const def of man) {
    const ten = `__xoa-nham-${def.step}.html`;
    const p = path.join(BUILD, ten);
    fs.writeFileSync(p, trang);
    viet.push(p);

    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    await page.goto(`http://127.0.0.1:${port}/${ten}#${def.frag}`, { waitUntil: "networkidle0" });
    await page
      .waitForFunction((n) => (document.body?.innerText ?? "").includes(n), { timeout: 20000 }, def.needle)
      .catch(() => {});

    const ungVien = await page.evaluate(timUngVien);
    const lay = ungVien.slice(0, TRAN_MOI_MAN);
    let chonDuoc = 0;
    let xoaChinh = 0;
    let xoaDoiChung = 0;
    let truot = 0;
    const viDu = [];

    for (const uv of lay) {
      const ok = await page.evaluate(chon, uv.chu, uv.tag, uv.lop);
      if (!ok) {
        await page.evaluate(doChon);
        truot++;
        continue;
      }
      const snippet = `${uv.selector} "${uv.chu}" is 92% covered by an opaque element (${uv.selector})`;
      const a = await chinh.phanLoai(page, { snippet });
      const b = await doiChung.phanLoai(page, { snippet });
      await page.evaluate(doChon);

      // Only burials that took, and only where BOTH readings saw the same
      // buried state, so the two columns describe one population.
      if (a.diemNhinThay !== 0 || b.diemNhinThay !== 0 || !a.diemDo || !b.diemDo) {
        truot++;
        continue;
      }
      chonDuoc++;
      if (!chinh.laLoiThat(a)) {
        xoaChinh++;
        if (viDu.length < 2) viDu.push(`XOA  ${a.verdict}  ${a.diemNhinThay}/${a.diemDo}  "${uv.chu}"`);
      }
      if (!doiChung.laLoiThat(b)) xoaDoiChung++;
    }

    bang.push({
      step: def.step,
      coThe: ungVien.length,
      thu: lay.length,
      chonDuoc,
      xoaChinh,
      xoaDoiChung,
      truot,
      viDu,
    });
    await page.close();
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  for (const p of viet) fs.rmSync(p, { force: true });
}

console.log(`module do      : ${DUONG_CHINH}`);
console.log(`doi chung      : che-chu.mjs @ ${SHA_DOI_CHUNG} (co duong tat to-cha)`);
console.log(`tran moi man   : ${TRAN_MOI_MAN} chu\n`);
console.log("man          co the  thu  chon that   xoa(do)  xoa(doi chung)");
let tChon = 0;
let tChinh = 0;
let tDoi = 0;
let tBoQua = 0;
for (const b of bang) {
  tChon += b.chonDuoc;
  tChinh += b.xoaChinh;
  tDoi += b.xoaDoiChung;
  tBoQua += Math.max(0, b.coThe - b.thu);
  console.log(
    `${b.step.padEnd(12)}${String(b.coThe).padStart(6)}${String(b.thu).padStart(5)}` +
      `${String(b.chonDuoc).padStart(11)}${String(b.xoaChinh).padStart(10)}${String(b.xoaDoiChung).padStart(16)}`,
  );
  for (const v of b.viDu) console.log(`             ${v}`);
}
const ty = (n) => (tChon ? ((n / tChon) * 100).toFixed(1) : "0.0") + "%";
console.log(`\nchu bi chon that : ${tChon}   (${tBoQua} vuot tran moi man, khong do)`);
console.log(`bi xoa nham (do)         : ${tChinh}/${tChon} = ${ty(tChinh)}`);
console.log(`bi xoa nham (doi chung)  : ${tDoi}/${tChon} = ${ty(tDoi)}`);

if (tChon === 0) {
  thoiChuaKetLuan("khong chon duoc chu nao -- lop phu khong dap trung, hoac man khong render.");
}
if (tDoi === 0) {
  thoiChuaKetLuan(
    "doi chung KHONG xoa gi. Ban pre-patch dang le phai xoa gan het; " +
      "so 0 o cot 'do' vi the khong chung minh duoc dieu gi.",
  );
}
if (tChinh > 0) {
  console.error(`\nHONG: ${tChinh}/${tChon} chu bi chon that van bi xoa.`);
  process.exit(1);
}
console.log(`\nDAT: doi chung xoa ${tDoi}/${tChon}, ban dang do xoa 0/${tChon}.`);
