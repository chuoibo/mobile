/** Image QA for the four hero screens, measured off rendered PIXELS.
 *
 * The demo path is chụp bill -> AI đọc món -> chia tiền -> VietQR, and its four
 * screens are `chup-bill`, `ket-qua`, `goi-y` and `ket-qua-thanh-toan`. They had
 * been walked (a Playwright pass in #330) and they had been through `imp detect`
 * (`quet-man-sau-tap.mjs`), and neither of those answers the questions this file
 * asks, for reasons each tool states about itself:
 *
 *   - `imp detect` computes contrast against CSS grounds. `soi-tuong-phan-anh.mjs`
 *     measured that blindness rather than assuming it: with the scrim flattened
 *     to [0,0,0] -- type on a near-white photo with nothing between -- the full
 *     URL scan still reported `findings= 0`. A CSS ground is not the ground.
 *   - `soi-tuong-phan-anh.mjs` does sample pixels, and cannot reach these four.
 *     It navigates `#${man.frag}` (line 227) and these screens have no fragment;
 *     they are reached by pressing through the app. So the tool that samples
 *     pixels cannot get here, and the tool that gets here does not sample pixels.
 *
 * That gap is the whole reason this file exists. It is not a third scanner: it
 * takes the walk from `quet-man-sau-tap.mjs` and the pixel technique from
 * `soi-tuong-phan-anh.mjs` and joins them, so the screens the product exists to
 * demonstrate get measured the way a person sees them.
 *
 * ## What it measures, and why each one is pixels rather than markup
 *
 *   A. CONTRAST. For every leaf text: hide JUST that text, screenshot the
 *      rectangle it occupied, and take the WORST pixel in it as the ground.
 *      Legibility is decided by the hardest spot in the box, so an average
 *      would hide a blown-out corner. This is ground-agnostic on purpose --
 *      photo, gradient, card or gradient-over-photo all answer the same way,
 *      and no declaration table has to be kept correct for it to look.
 *   B. TAP TARGETS. Rendered rectangles of interactive elements against 44px.
 *      A style object saying `height: 44` is not a measurement; a row that
 *      collapsed under flex still declares 44 in the source.
 *   C. OCCLUSION at 390x844. `elementsFromPoint` at the middle of the word,
 *      after scrolling it into view. Box arithmetic reports text that merely
 *      scrolled out of a container as "covered" -- this repo has been burned by
 *      that three times (`che-chu.mjs`), so the question is asked the way a
 *      reader answers it: is the word the topmost thing painted at its own
 *      centre. Overflow past the viewport edge is measured separately.
 *   D. THE VietQR, DECODED FROM THE SCREENSHOT. `MaVietQr.tsx` paints one View
 *      per module, so the DOM holds hundreds of divs whether or not anything
 *      legible reached the glass. Counting them proves nothing. The region is
 *      screenshotted and handed to OpenCV -- a decoder sharing no code with
 *      `qr.ts` -- and the bytes that come back must equal the payload that went
 *      in. That is the difference between "an element exists" and "a bank app
 *      could scan this".
 *
 * ## Why the screen it names is the screen it measured
 *
 * A self-driving page has a race: measure before the walk lands and you score
 * the opening screen under the target screen's name. `quet-man-sau-tap.mjs`
 * solves it for an external scanner with a colour canary, because it cannot see
 * into the page. This file drives the page itself, so it reads the walk's own
 * completion flag -- `window.__lai.xong` -- and additionally requires the
 * screen's needle to be present. A walk that threw sets `__lai.loi` and the
 * screen is refused rather than measured. No number is printed for a screen
 * whose walk did not finish.
 *
 * ## What it does NOT prove
 *
 * That a real bank app acquires the code off a real phone screen in a dim
 * restaurant (needs a phone, an account and a camera). That a person understands
 * what they are looking at. That the screens are correct in any state other than
 * the one this walk produces -- one bill, three eaters, one currency, light
 * mode, 390x844. Nothing here is a substitute for a human looking at the demo.
 *
 * Dev tool, not shipped code. Nothing in the app may import it. The generated
 * page stubs the API and is deleted on the way out.
 *
 *     cd apps/mobile && npm run build:check && node tools/anh-bon-man-hero.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, VIETQR_FIXTURE, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const BUILD = path.join(MOBILE_ROOT, ".expo-build-check");

/** The phone, stated rather than defaulted: every rule here answers differently
 *  per width, and an unstated width makes two runs incomparable. */
const RONG = 390;
const CAO = 844;

/** AA. 4.5:1 for body text, 3:1 for text large enough to earn the relief
 *  (>=24px, or >=18.66px when bold). */
const AA_THUONG = 4.5;
const AA_LON = 3.0;

/** The leader asked for 44, which is Apple's HIG and Android's 48dp rounded
 *  down -- stricter than WCAG 2.2 AA's 24x24 (2.5.8). Both are reported so a
 *  reader can tell a HIG miss from a WCAG failure. */
const CHAM_MONG_MUON = 44;
const CHAM_WCAG = 24;

/** The four screens this file exists for, named by their walk step. */
const BON_MAN = ["chup-bill", "ket-qua", "goi-y", "ket-qua-thanh-toan"];

const raDir = process.env.ANH_RA ?? path.join(MOBILE_ROOT, ".anh-bon-man");

/* ------------------------------------------------------------------ colour */

/** sRGB relative luminance, WCAG 2.x definition. */
function sang(r, g, b) {
  const f = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function tuongPhan(a, b) {
  const l1 = sang(...a);
  const l2 = sang(...b);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** `rgb(r, g, b)` / `rgba(...)` as computed by the engine. */
function docMau(css) {
  const m = String(css).match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(",").map((s) => parseFloat(s.trim()));
  if (p.length < 3 || p.some((n) => Number.isNaN(n))) return null;
  return [p[0], p[1], p[2]];
}

/* ------------------------------------------------------- in-page collectors */

/** Every leaf text box, with the colour and size the engine resolved.
 *
 * Leaf only: a wrapper's box spans its children and would be measured against
 * ground its own glyphs never touch. */
function thuChu() {
  const ra = [];
  let n = 0;
  for (const e of document.querySelectorAll("div, span, p, a, li, h1, h2, h3, h4, button")) {
    if (e.children.length !== 0) continue;
    const chu = (e.textContent ?? "").trim();
    if (!chu) continue;
    const st = getComputedStyle(e);
    if (st.visibility === "hidden" || st.display === "none" || parseFloat(st.opacity) === 0) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    // Outside the viewport entirely: not on the glass, so not this run's claim.
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) continue;
    e.setAttribute("data-anh-chu", String(n));
    ra.push({
      id: n++,
      chu: chu.slice(0, 60),
      x: r.x, y: r.y, w: r.width, h: r.height,
      mau: st.color,
      co: parseFloat(st.fontSize),
      dam: st.fontWeight,
    });
  }
  return ra;
}

/** Interactive elements, as the engine lays them out.
 *
 * `react-native-web` renders Pressable as a div carrying role=button and
 * tabindex, so those two plus real buttons/links cover what a finger can hit. */
function thuNut() {
  const sel = '[role="button"], button, a[href], [tabindex]:not([tabindex="-1"]), input, [role="checkbox"], [role="radio"], [role="switch"]';
  const ra = [];
  let n = 0;
  for (const e of document.querySelectorAll(sel)) {
    const st = getComputedStyle(e);
    if (st.visibility === "hidden" || st.display === "none" || parseFloat(st.opacity) === 0) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) continue;
    // Nested pressables: an inner control inherits the outer one's hit area
    // only if the outer one is also a target, so both are reported and the
    // reader decides. Labelled by text so the row is identifiable.
    ra.push({
      id: n++,
      nhan: (e.getAttribute("aria-label") || e.textContent || "").trim().slice(0, 50),
      the: e.tagName.toLowerCase(),
      vaiTro: e.getAttribute("role") || "",
      x: r.x, y: r.y, w: r.width, h: r.height,
    });
  }
  return ra;
}

/**
 * Occlusion, asked the way a reader answers it.
 *
 * Scroll the words into view, then ask the engine what is painted at the middle
 * of the word. `elementsFromPoint` has already resolved paint order, stacking
 * contexts, transforms and clipping, so there is no box arithmetic left to be
 * wrong about. A word is covered when the topmost element at its own centre is
 * neither itself nor one of its descendants.
 */
function soiCheChu() {
  const ra = [];
  for (const e of document.querySelectorAll("[data-anh-chu]")) {
    const chu = (e.textContent ?? "").trim();
    if (!chu) continue;
    e.scrollIntoView({ block: "center", inline: "nearest" });
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cx = r.x + r.width / 2;
    const cy = r.y + r.height / 2;
    if (cx < 0 || cy < 0 || cx >= innerWidth || cy >= innerHeight) continue;
    const stack = document.elementsFromPoint(cx, cy);
    if (!stack.length) continue;
    const tren = stack[0];
    if (tren === e || e.contains(tren) || tren.contains(e)) continue;
    const st = getComputedStyle(tren);
    ra.push({
      chu: chu.slice(0, 60),
      boi: (tren.getAttribute("aria-label") || tren.textContent || tren.tagName).trim().slice(0, 50),
      mo: st.opacity,
      nen: st.backgroundColor,
    });
  }
  return ra;
}

/** Text whose box crosses the viewport's left/right edge.
 *
 * Horizontal only: vertical extent is what scrolling is for, and calling it
 * overflow would flag every long screen. */
function soiTranVien(rong) {
  const ra = [];
  for (const e of document.querySelectorAll("[data-anh-chu]")) {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (r.left >= -0.5 && r.right <= rong + 0.5) continue;
    ra.push({
      chu: (e.textContent ?? "").trim().slice(0, 60),
      trai: Math.round(r.left * 10) / 10,
      phai: Math.round(r.right * 10) / 10,
    });
  }
  return ra;
}

/* --------------------------------------------------------------- the ground */

/**
 * The worst legible spot in one text box, measured from rendered pixels only.
 *
 * ## Why the CSS colour is not used, and what it cost to learn
 *
 * The first version of this function read `getComputedStyle(e).color` as the
 * text colour and sampled only the ground. On `chup-bill` it reported 21.00:1
 * for every one of the nine strings, including two the eye reads as clearly
 * dimmer. The palette is the reason: this app writes secondary type as
 * `rgba(255, 255, 255, 0.62)`, and dropping the alpha turns 62%-white into
 * pure white -- the exact class of defect the measurement exists to catch,
 * scored as the best possible result. A tool blind to translucent type on a
 * dark screen would have passed this whole demo path.
 *
 * Compositing the alpha by hand would fix that one case and not the next:
 * ancestor `opacity`, blend modes, filters and a translucent scrim stack on top
 * of each other, and every one of them is another rule to reimplement and get
 * wrong. The engine already resolves all of it, so the answer is taken from the
 * engine's output rather than recomputed from its input.
 *
 * ## The measurement
 *
 * Two screenshots of the same rectangle: one with the text, one with it hidden
 * (`visibility: hidden` rather than removed, so the layout does not reflow and
 * the rectangle stays the rectangle the glyphs occupied).
 *
 *   - a pixel that CHANGED between the two is a glyph pixel;
 *   - the ones that changed MOST are glyph interior, the rest anti-aliased edge.
 *     Edges are excluded deliberately: an edge pixel is a blend of ink and
 *     ground and always scores badly, so including them would flag every screen
 *     on earth;
 *   - each interior pixel is contrasted against the ground AT THAT SAME PIXEL,
 *     from the without-text shot -- so type on a photograph is judged against
 *     the part of the photograph actually under it, not an average;
 *   - the worst of those is the answer, because legibility is decided by the
 *     hardest spot in the box.
 *
 * Nothing here reads a colour, an alpha or a background from CSS, so a ground
 * that is a photo, a gradient, a scrim over a photo, or a plain card all answer
 * the same way and no declaration table has to be kept true for it to look.
 *
 * A box whose pixels do not change at all is reported as `veKhongRa`: the text
 * is in the DOM and put no ink on the glass. That is a finding, not a 21:1.
 */
async function nenTeNhat(page, id, o) {
  const chup = async () => await page.screenshot({ encoding: "base64", clip: o });
  const co = await chup();
  await page.evaluate((i) => {
    const e = document.querySelector(`[data-anh-chu="${i}"]`);
    if (e) e.style.visibility = "hidden";
  }, id);
  let khong;
  try {
    khong = await chup();
  } finally {
    await page.evaluate((i) => {
      const e = document.querySelector(`[data-anh-chu="${i}"]`);
      if (e) e.style.visibility = "";
    }, id);
  }
  return await page.evaluate(
    async (a, b) => {
      const doc = async (s) => {
        const im = new Image();
        // repo-guard: allow=data-uri-base64 reason=anh-chup-man-luc-do
        im.src = `data:image/png;base64,${s}`;
        await im.decode();
        const c = document.createElement("canvas");
        c.width = im.naturalWidth;
        c.height = im.naturalHeight;
        const x = c.getContext("2d");
        x.drawImage(im, 0, 0);
        return x.getImageData(0, 0, c.width, c.height).data;
      };
      const A = await doc(a);
      const B = await doc(b);
      if (A.length !== B.length) return { veKhongRa: true, te: null };

      const sang = (r, g, bl) => {
        const f = (v) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl);
      };

      let dMax = 0;
      for (let i = 0; i < A.length; i += 4) {
        const d = Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]);
        if (d > dMax) dMax = d;
      }
      // Below this the box put no ink anywhere: invisible text, not good text.
      if (dMax < 8) return { veKhongRa: true, te: null };

      /* The ink colour is the MOST-covered pixel; only the ground is worst-case.
       *
       * The obvious version -- minimum of contrast(ink_i, ground_i) over every
       * well-covered pixel -- is biased low, and the bias lands exactly on the
       * AA boundary where it does the most damage. Anti-aliasing means coverage
       * is a gradient, so the admitted band always contains pixels that are 90%
       * ink and 10% ground; scoring those measures the blur, not the design.
       * Measured on this screen: white-on-black type read 20.12:1 (true 21.00),
       * and `← Đóng` read 4.45:1 against a true 4.555:1 -- turning a string that
       * PASSES AA into a reported failure. Raising the device pixel ratio to 4
       * and 8 changed neither number, which is what ruled out sampling
       * resolution and pointed at the statistic instead.
       *
       * So: the pixel that changed most is the closest thing on screen to the
       * composited ink colour, and it is taken as the ink. The ground is still
       * the worst pixel anywhere under the glyphs, because legibility really is
       * decided by the hardest spot in the box -- that half of the original
       * reasoning was right and is kept. */
      let iInk = -1;
      for (let i = 0; i < A.length; i += 4) {
        const d = Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]);
        if (d >= dMax) { iInk = i; break; }
      }
      if (iInk < 0) return { veKhongRa: true, te: null };
      const chuPx = [A[iInk], A[iInk + 1], A[iInk + 2]];
      const lInk = sang(chuPx[0], chuPx[1], chuPx[2]);

      /* Ground sampled only where the glyphs actually sit. Half coverage is the
       * cut: below that the pixel is mostly ground the reader sees around the
       * word rather than through it, and a card edge two pixels away would
       * otherwise decide the verdict for the word. */
      const nguongNen = 0.5 * dMax;
      let te = Infinity;
      let nenPx = null;
      for (let i = 0; i < A.length; i += 4) {
        const d = Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]);
        if (d < nguongNen) continue;
        const lN = sang(B[i], B[i + 1], B[i + 2]);
        const [hi, lo] = lInk >= lN ? [lInk, lN] : [lN, lInk];
        const t = (hi + 0.05) / (lo + 0.05);
        if (t < te) {
          te = t;
          nenPx = [B[i], B[i + 1], B[i + 2]];
        }
      }
      if (!Number.isFinite(te)) return { veKhongRa: true, te: null };
      return { veKhongRa: false, te, px: nenPx, chuPx };
    },
    co,
    khong,
  );
}

/* ------------------------------------------------------------------ the QR */

/**
 * Decode the VietQR out of a screenshot of the rendered screen.
 *
 * OpenCV shares no code, no author and no assumptions with `src/ui/qr.ts`, so a
 * payload that survives the round trip proves the modules reached the glass in a
 * state something else can read -- which is the question, and which no DOM
 * assertion can answer about a code drawn as hundreds of Views.
 */
function giaiQr(pngPath) {
  const py = `
import sys, cv2
img = cv2.imread(sys.argv[1])
if img is None:
    print("LOI:khong-doc-duoc-anh"); sys.exit(0)
d = cv2.QRCodeDetector()
try:
    txt, pts, _ = d.detectAndDecode(img)
except Exception as e:
    print("LOI:" + str(e)); sys.exit(0)
print("OK:" + (txt or ""))
`;
  try {
    const out = execFileSync("python3", ["-c", py, pngPath], { encoding: "utf8", timeout: 60000 });
    const s = out.trim();
    if (s.startsWith("OK:")) return { ok: true, text: s.slice(3) };
    return { ok: false, loi: s.replace(/^LOI:/, "") };
  } catch (e) {
    return { ok: false, loi: String(e.message || e) };
  }
}

/* -------------------------------------------------------------------- drive */

async function doMotMan(browser, port, man, tenTrang) {
  const page = await browser.newPage();
  page.setDefaultTimeout(120000);
  const url = `http://127.0.0.1:${port}/${tenTrang}`;
  await page.goto(url, { waitUntil: "networkidle0", timeout: 120000 });

  /* The walk's own flag, not a guess about timing. A screen whose walk threw is
   * refused; measuring it would print the opening screen's numbers under this
   * screen's name, which is the one failure this whole file would not survive. */
  await page.waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), { timeout: 120000 });
  const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
  if (lai.loi) throw new Error(`${man.step}: kịch bản đi bộ HỎNG: ${lai.loi}`);
  if (!lai.xong) throw new Error(`${man.step}: kịch bản đi bộ chưa xong`);

  const coNeedle = await page.evaluate((n) => (document.body?.innerText ?? "").includes(n), man.needle);
  if (!coNeedle) throw new Error(`${man.step}: đi bộ xong nhưng không thấy "${man.needle}" — đo sẽ là đo màn khác`);

  // Let the last paint settle; fonts and any transition finish before pixels
  // are believed.
  await page.evaluate(() => document.fonts?.ready);
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
  await new Promise((r) => setTimeout(r, 300));

  fs.mkdirSync(raDir, { recursive: true });
  const anhMan = path.join(raDir, `${man.step}.png`);
  await page.screenshot({ path: anhMan, fullPage: false });

  const chus = await page.evaluate(thuChu);
  const nuts = await page.evaluate(thuNut);

  /* Contrast, one screenshot per text box. Done before occlusion, because
   * `soiCheChu` scrolls and every rectangle collected above would move. */
  const kem = [];
  const veKhongRa = [];
  let teNhat = null;
  for (const c of chus) {
    const clip = {
      x: Math.max(0, Math.floor(c.x)),
      y: Math.max(0, Math.floor(c.y)),
      width: Math.min(Math.ceil(c.w), RONG - Math.max(0, Math.floor(c.x))),
      height: Math.min(Math.ceil(c.h), CAO - Math.max(0, Math.floor(c.y))),
    };
    if (clip.width < 1 || clip.height < 1) continue;
    const { te, px, chuPx, veKhongRa: khong } = await nenTeNhat(page, c.id, clip);
    const lon = c.co >= 24 || (c.co >= 18.66 && Number(c.dam) >= 700);
    const nguong = lon ? AA_LON : AA_THUONG;
    if (khong) {
      // Adjudicated after the loop -- see `cuonRoiDo`. Scrolling here would
      // move every rectangle still to be measured.
      veKhongRa.push({ chu: c.chu, mau: c.mau, co: c.co, id: c.id });
      if (process.env.ANH_CHITIET) console.log(`     . VE KHONG RA (cho xet)  ${c.co}px chu=${c.mau} "${c.chu}"`);
      continue;
    }
    if (process.env.ANH_CHITIET) {
      console.log(
        `     . ${te.toFixed(2)}:1 can=${nguong} ${c.co}px khai=${c.mau} ve=rgb(${chuPx}) nen=rgb(${px}) "${c.chu}"`,
      );
    }
    if (!teNhat || te < teNhat.te) teNhat = { te, chu: c.chu };
    if (te < nguong) {
      kem.push({ chu: c.chu, te: Math.round(te * 100) / 100, nguong, co: c.co, mau: c.mau, ve: chuPx, nen: px });
    }
  }

  /* Adjudicate the boxes that put no ink on the glass, and measure them.
   *
   * "Drew nothing" has two causes that look identical from one screenshot, and
   * only one of them is a defect:
   *
   *   - the words sit below the fold of an INNER scroll container, so the
   *     screenshot of their rectangle is whatever is painted at those
   *     coordinates and hiding them changes nothing. This is the artifact
   *     `che-chu.mjs` exists for, and it caught six strings here: on `goi-y`
   *     the item list lives in a 164px box holding 326px of rows, clip edge at
   *     y=567, first row at y=569. Reporting those as invisible would have been
   *     a fabricated defect about a product that is behaving.
   *   - the words are genuinely painted nowhere. That one is real.
   *
   * So the question gets asked the way a reader answers it: scroll to them and
   * look again. Scrolling also buys back coverage that was silently missing --
   * before this pass, every string below an inner fold went unmeasured for
   * contrast, which is its own quiet hole.
   */
  const cuonKhuat = [];
  const veThat = [];
  for (const v of veKhongRa) {
    await page.evaluate((i) => {
      const e = document.querySelector(`[data-anh-chu="${i}"]`);
      if (e) e.scrollIntoView({ block: "center", inline: "nearest" });
    }, v.id);
    const r = await page.evaluate((i) => {
      const e = document.querySelector(`[data-anh-chu="${i}"]`);
      if (!e) return null;
      const b = e.getBoundingClientRect();
      return { x: b.x, y: b.y, w: b.width, h: b.height };
    }, v.id);
    if (!r || r.w < 1 || r.h < 1) { veThat.push({ ...v, vi: "khong con hop" }); continue; }
    const clip = {
      x: Math.max(0, Math.floor(r.x)),
      y: Math.max(0, Math.floor(r.y)),
      width: Math.min(Math.ceil(r.w), RONG - Math.max(0, Math.floor(r.x))),
      height: Math.min(Math.ceil(r.h), CAO - Math.max(0, Math.floor(r.y))),
    };
    if (clip.width < 1 || clip.height < 1) { veThat.push({ ...v, vi: "ngoai khung sau khi cuon" }); continue; }
    const lai = await nenTeNhat(page, v.id, clip);
    if (lai.veKhongRa) {
      veThat.push({ ...v, vi: "cuon toi noi van khong len pixel" });
      continue;
    }
    const lon = v.co >= 24 || (v.co >= 18.66 && Number(v.dam) >= 700);
    const nguong = lon ? AA_LON : AA_THUONG;
    cuonKhuat.push({ ...v, te: Math.round(lai.te * 100) / 100, nguong });
    if (!teNhat || lai.te < teNhat.te) teNhat = { te: lai.te, chu: v.chu };
    if (lai.te < nguong) {
      kem.push({ chu: v.chu, te: Math.round(lai.te * 100) / 100, nguong, co: v.co, mau: v.mau, ve: lai.chuPx, nen: lai.px, cuon: true });
    }
  }

  const chamKem = nuts
    .filter((n) => n.w < CHAM_MONG_MUON || n.h < CHAM_MONG_MUON)
    .map((n) => ({
      nhan: n.nhan,
      the: n.the,
      vaiTro: n.vaiTro,
      w: Math.round(n.w * 10) / 10,
      h: Math.round(n.h * 10) / 10,
      duoiWcag: n.w < CHAM_WCAG || n.h < CHAM_WCAG,
    }));

  const tran = await page.evaluate(soiTranVien, RONG);
  const che = await page.evaluate(soiCheChu);

  /* The QR: only where one exists. The region is the biggest square-ish block
   * on the screen carrying the module Views, found by geometry rather than by a
   * test id, so a refactor that renames things does not silently stop looking. */
  let qr = null;
  if (man.step === "ket-qua-thanh-toan") {
    await page.evaluate(() => window.scrollTo(0, 0));
    const o = await page.evaluate(() => {
      let best = null;
      for (const e of document.querySelectorAll("div")) {
        const r = e.getBoundingClientRect();
        if (r.width < 80 || r.height < 80) continue;
        if (Math.abs(r.width - r.height) > 12) continue;
        // A QR block is made of many small children; a plain card is not.
        if (e.querySelectorAll("div").length < 100) continue;
        if (!best || r.width > best.width) {
          best = { x: r.x, y: r.y, width: r.width, height: r.height, con: e.querySelectorAll("div").length };
        }
      }
      return best;
    });
    if (!o) {
      qr = { tim: false };
    } else {
      const clip = {
        x: Math.max(0, Math.floor(o.x)),
        y: Math.max(0, Math.floor(o.y)),
        width: Math.ceil(o.width),
        height: Math.ceil(o.height),
      };
      const anhQr = path.join(raDir, "vietqr.png");
      await page.screenshot({ path: anhQr, clip });
      const g = giaiQr(anhQr);
      qr = { tim: true, con: o.con, w: Math.round(o.width), h: Math.round(o.height), anh: anhQr, ...g };
    }
  }

  await page.close();
  return { step: man.step, anh: anhMan, soChu: chus.length, soNut: nuts.length, teNhat, kem, cuonKhuat, veThat, chamKem, tran, che, qr };
}

/* --------------------------------------------------------------------- main */

async function main() {
  const chi = process.env.ANH_MAN ? process.env.ANH_MAN.split(",") : BON_MAN;
  const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");

  const trangs = [];
  for (const step of chi) {
    const man = MAN_SAU_TAP.find((m) => m.step === step);
    if (!man) throw new Error(`khong co man "${step}" trong MAN_SAU_TAP`);
    const ten = `__anh-${step}.html`;
    fs.writeFileSync(path.join(BUILD, ten), trangTuLai(indexHtml, man.kichBan, null));
    trangs.push({ man, ten });
  }

  const server = createStaticServer(BUILD);
  let browser;
  const ketQua = [];
  try {
    const port = await listen(server);
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: { width: RONG, height: CAO, deviceScaleFactor: Number(process.env.ANH_DPR ?? 2), isMobile: true, hasTouch: true },
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        /* Grayscale anti-aliasing, not LCD subpixel.
         *
         * With subpixel AA on, white glyphs come back tinted -- rgb(143,215,255)
         * was measured on this screen's "Huỷ" -- because each channel is sampled
         * at a different horizontal offset. Those fringes are not colours anyone
         * chose, and contrasting them against the ground measures the renderer's
         * filter rather than the design. A phone composites the same way this
         * flag does, so this is also the closer model of the target device. */
        "--disable-lcd-text",
      ],
    });
    console.log(`== do hinh anh ${trangs.length} man hero, ${RONG}x${CAO}, pixel that ==`);
    for (const { man, ten } of trangs) {
      const t0 = Date.now();
      const r = await doMotMan(browser, port, man, ten);
      r.giay = ((Date.now() - t0) / 1000).toFixed(1);
      ketQua.push(r);
      console.log(`  -- ${r.step}: ${r.soChu} chu, ${r.soNut} diem cham, ${r.giay}s`);
    }
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
    for (const { ten } of trangs) fs.rmSync(path.join(BUILD, ten), { force: true });
  }

  // ------------------------------------------------------------------ report
  let loi = 0;
  console.log("");
  for (const r of ketQua) {
    console.log(`== ${r.step} ==  (anh: ${path.relative(MOBILE_ROOT, r.anh)})`);
    console.log(
      `   tuong phan: te nhat ${r.teNhat ? `${r.teNhat.te.toFixed(2)}:1 o "${r.teNhat.chu}"` : "khong do duoc"}` +
        `  -- ${r.kem.length} chu duoi AA`,
    );
    for (const k of r.kem) {
      loi += 1;
      console.log(
        `     [DUOI AA] ${k.te}:1 (can ${k.nguong}) ${k.co}px  "${k.chu}"  khai=${k.mau} ve=rgb(${k.ve}) nen=rgb(${k.nen})`,
      );
    }
    for (const v of r.veThat) {
      loi += 1;
      console.log(`     [VE KHONG RA] "${v.chu}" ${v.co}px khai=${v.mau} — ${v.vi}`);
    }
    /* Not a finding, and printed anyway: a reader who sees only "0 phat hien"
     * cannot tell a screen with nothing below the fold from a screen whose list
     * is one scroll away, and on `goi-y` that difference is the whole card. */
    if (r.cuonKhuat.length) {
      console.log(
        `   cuon khuat: ${r.cuonKhuat.length} chu nam duoi fold cua khung cuon TRONG man ` +
          "(khong phai loi — da cuon toi va do duoc)",
      );
      for (const v of r.cuonKhuat) console.log(`     - ${v.te}:1 (can ${v.nguong}) "${v.chu}"`);
    }
    console.log(`   diem cham: ${r.chamKem.length} duoi ${CHAM_MONG_MUON}px`);
    /* Counted against 44, which is the bar this run was asked for (Apple HIG;
     * Android asks 48dp). WCAG 2.2 AA 2.5.8 only asks 24x24, so the label says
     * which line a row crosses -- a reader deciding whether to block a release
     * needs to see that difference, and a single "fail" would hide it. */
    for (const c of r.chamKem) {
      loi += 1;
      console.log(
        `     [${c.duoiWcag ? "DUOI WCAG 24" : "DUOI HIG 44 (dat WCAG 24)"}] ${c.w}x${c.h}  ` +
          `<${c.the}${c.vaiTro ? ` role=${c.vaiTro}` : ""}>  "${c.nhan}"`,
      );
    }
    console.log(`   tran vien: ${r.tran.length}   che chu: ${r.che.length}`);
    for (const t of r.tran) {
      loi += 1;
      console.log(`     [TRAN VIEN] "${t.chu}"  trai=${t.trai} phai=${t.phai} (rong ${RONG})`);
    }
    for (const c of r.che) {
      loi += 1;
      console.log(`     [CHE CHU] "${c.chu}" bi che boi "${c.boi}" (nen=${c.nen}, opacity=${c.mo})`);
    }
    if (r.qr) {
      if (!r.qr.tim) {
        loi += 1;
        console.log("   VietQR: [KHONG TIM THAY] khong co khoi module nao tren man nay");
      } else if (!r.qr.ok) {
        loi += 1;
        console.log(`   VietQR: [KHONG GIAI DUOC] ${r.qr.w}x${r.qr.h}, ${r.qr.con} module-view -- ${r.qr.loi}`);
      } else if (r.qr.text !== VIETQR_FIXTURE) {
        loi += 1;
        console.log(`   VietQR: [SAI PAYLOAD] giai ra ${r.qr.text.length} ky tu, khac payload da gui`);
      } else {
        console.log(
          `   VietQR: OK -- ${r.qr.w}x${r.qr.h}px, ${r.qr.con} module-view, OpenCV giai lai DUNG ` +
            `${r.qr.text.length} ky tu payload tu ANH CHUP`,
        );
      }
    }
    console.log("");
  }

  console.log(loi ? `TONG: ${loi} phat hien` : "TONG: 0 phat hien");
  if (process.env.ANH_JSON) fs.writeFileSync(process.env.ANH_JSON, JSON.stringify(ketQua, null, 2));
  process.exit(loi ? 1 : 0);
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(2);
});
