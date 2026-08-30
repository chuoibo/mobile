/** Do the dish rows on `goi-y` put INK on the glass -- measured from the picture.
 *
 * `tests/mon-tren-goi-y.test.mjs` already gates this screen, and it gates it by
 * geometry: the row's box against the scroller's clip box, both read out of the
 * DOM. That is the right question and it caught the real defect, but it is not
 * the question the leader asked, which was to see the screen.
 *
 * The gap between the two is not theoretical in this repo:
 *
 *   - `full_page` screenshots on react-native-web captured the wrong frame
 *     entirely: 102 text assertions passed against a picture with no cards in
 *     it. Text that the DOM swears is placed can be absent from the render.
 *   - A box inside its clip box still paints nothing if it is `opacity: 0`, the
 *     same colour as its ground, covered by a later sibling, or waiting on a
 *     font that never loaded. Every one of those reads as a pass to a
 *     `getBoundingClientRect` gate.
 *
 * So this probe never asks the DOM where anything is. It shoots the 390x844
 * viewport, hides ONE dish name, shoots the identical viewport again, and
 * counts pixels that changed. A pixel that changes when a string is hidden is a
 * pixel that string was painting, and it is inside the frame by construction --
 * which is the whole claim, "visible when the screen finishes drawing".
 *
 * `visibility: hidden` keeps the box, so nothing reflows and the second shot
 * samples the same places as the first. The technique is the one
 * `soi-tuong-phan-anh.mjs` uses for text-on-photograph, applied to a scroller.
 *
 * A row scrolled under the fold changes exactly zero pixels. A row sliced by
 * the clip edge changes a few. A row on the glass changes thousands. The
 * counts, and the bounding box of what changed, are printed rather than judged
 * here -- `tests/muc-hang-mon-goi-y.test.mjs` is where the threshold lives.
 *
 * Reads a build, does not make one. Point it at either side of a fix:
 *
 *     cd apps/mobile
 *     MOBILE_WEB_EXPORT=/tmp/ph3-truoc/apps/mobile/.expo-build-check \
 *     PH3_NHAN=truoc node tools/anh-hang-mon-goi-y.mjs
 *
 * PNGs land in `PH3_ANH` (default /tmp/ph3-anh) and never in git: the repo
 * guard fails closed on new binaries and it is right to.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = process.env.MOBILE_WEB_EXPORT ?? path.join(path.resolve(HERE, ".."), ".expo-build-check");
const NHAN = process.env.PH3_NHAN ?? "man";
const ANH = process.env.PH3_ANH ?? "/tmp/ph3-anh";

/** The phone the demo runs on. The defect is height-dependent; this is not a
 *  detail that can be generalised away. */
export const RONG = 390;
export const CAO = 844;

/** The three dishes on the fixture bill, and the three group members a person
 *  adds first. Both counts are asserted before any pixel is read: "found no
 *  rows" must never be reported as "no row is hidden". */
export const MON = ["Lẩu thái", "Nước sâm", "Cơm rang"];
export const THEM = ["Minh", "Trang", "Hải"];

/* --------------------------------------------------------------- in-page --- */

/** Hide (or restore) the leaf node whose whole text is `t`.
 *
 *  Leaf only: a container that merely contains the dish name in its subtree
 *  would hide the entire card and every count would come back enormous and
 *  meaningless. Returns false when no such node exists, which the caller turns
 *  into a hard failure rather than a zero. */
function anChu(t, an) {
  for (const e of document.querySelectorAll("div, span")) {
    if (e.children.length === 0 && (e.textContent ?? "").trim() === t) {
      e.style.visibility = an ? "hidden" : "";
      return true;
    }
  }
  return false;
}

/** Decode two PNGs through a canvas and report what differs.
 *
 *  Done in the page because the browser already has a PNG decoder that is
 *  certainly correct; a decoder written here would be a second thing to be
 *  wrong. The bounding box matters as much as the count: a row sliced by the
 *  clip edge and a row on the glass can both be "some pixels", and only the
 *  box height tells them apart. */
async function soHaiAnh(a, b) {
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
    return { d: x.getImageData(0, 0, c.width, c.height).data, w: c.width, h: c.height };
  };
  const A = await doc(a);
  const B = await doc(b);
  let doi = 0;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -1;
  let y1 = -1;
  for (let i = 0; i < A.d.length; i += 4) {
    if (A.d[i] !== B.d[i] || A.d[i + 1] !== B.d[i + 1] || A.d[i + 2] !== B.d[i + 2]) {
      doi += 1;
      const p = i / 4;
      const x = p % A.w;
      const y = Math.floor(p / A.w);
      if (x < x0) x0 = x;
      if (y < y0) y0 = y;
      if (x > x1) x1 = x;
      if (y > y1) y1 = y;
    }
  }
  return {
    doi,
    // Device pixels. The viewport is shot at deviceScaleFactor 2, so these are
    // reported as-is and halved only where a CSS number is meant.
    hop: doi ? { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 } : null,
    khung: { w: A.w, h: A.h },
  };
}

/* ------------------------------------------------------------------ probe --- */

/**
 * Two consecutive frames that are byte-identical, or null after `lan` tries.
 *
 * Without this the probe reports animation as ink. Measured on the pre-fix
 * build, state B: hiding "Cơm rang" came back 5952 changed pixels in a box at
 * CSS y=215, while the DOM put that row at y=710 and off the fold -- the
 * difference was something still moving on screen, and it would have been
 * written up as "one dish row is visible" on a build where none was.
 *
 * A settled frame is the control this measurement rests on, the same way a
 * clean canary is what makes a dirty canary's count mean anything.
 */
async function choYen(page, lan = 40) {
  let truoc = await page.screenshot({ encoding: "base64" });
  for (let i = 0; i < lan; i += 1) {
    await new Promise((r) => setTimeout(r, 100));
    const sau = await page.screenshot({ encoding: "base64" });
    if (sau === truoc) return sau;
    truoc = sau;
  }
  return null;
}

/** One dish: base frame vs frame with that dish hidden.
 *
 *  The base is taken twice with nothing changed between them. If those two
 *  differ, the frame is still moving and every number from it is noise, so the
 *  dish is reported `yen: false` rather than given a count. A probe that cannot
 *  tell ink from motion has to say so, not pick the flattering reading. */
async function doMucMot(page, ten) {
  const co = await choYen(page);
  if (co === null) return { ten, timThay: true, yen: false };

  const thay = await page.evaluate(anChu, ten, true);
  if (!thay) {
    await page.evaluate(anChu, ten, false);
    return { ten, timThay: false };
  }
  const khong = await page.screenshot({ encoding: "base64" });
  await page.evaluate(anChu, ten, false);
  if (co === khong) return { ten, timThay: true, yen: true, doi: 0, hop: null };
  const ra = await page.evaluate(soHaiAnh, co, khong);
  return { ten, timThay: true, yen: true, ...ra };
}

/** Every dish on the current screen, plus the frame itself saved to disk. */
async function doMan(page, nhan, anhDir, tienTo) {
  fs.mkdirSync(anhDir, { recursive: true });
  const duong = path.join(anhDir, `${tienTo}-${nhan}.png`);
  // Settle before the keepsake shot too, so the PNG a person opens is the same
  // frame the counts below were taken from.
  await choYen(page);
  // Viewport only. NOT fullPage: on react-native-web a full-page capture has
  // been measured shooting a frame the user never sees, and the whole question
  // here is what is on the glass at 390x844.
  await page.screenshot({ path: duong });

  const hang = [];
  for (const t of MON) hang.push(await doMucMot(page, t));
  return { nhan, anh: duong, hang };
}

function inRa(ra) {
  console.log(`\n[${ra.nhan}]  ${ra.anh}`);
  for (const h of ra.hang) {
    if (!h.timThay) {
      console.log(`  ${h.ten.padEnd(10)} KHÔNG CÓ TRONG DOM`);
      continue;
    }
    if (!h.yen) {
      console.log(`  ${h.ten.padEnd(10)} KHUNG CHƯA YÊN — số đo vô nghĩa`);
      continue;
    }
    const hop = h.hop ? `hộp ${h.hop.w}x${h.hop.h} @ y=${h.hop.y}` : "không đổi pixel nào";
    console.log(`  ${h.ten.padEnd(10)} mực=${String(h.doi).padStart(6)} px  ${hop}`);
  }
  const co = ra.hang.filter((h) => h.timThay && h.yen && h.doi > 0).length;
  console.log(`  => ${co}/${MON.length} hàng món CÓ MỰC trên khung 390x844`);
}

/* ------------------------------------------------------------------- đo --- */

/**
 * Both states of `goi-y` on one build, measured from the pictures.
 *
 * Exported so `tests/muc-hang-mon-goi-y.test.mjs` gates exactly what this
 * prints: one implementation, so the gate and the evidence in a PR description
 * can never drift into describing two different measurements.
 */
export async function doMucHangMon({ build = BUILD, nhan = NHAN, anhDir = ANH } = {}) {
if (!fs.existsSync(path.join(build, "index.html"))) {
  throw new Error(`không có bản dựng web ở ${build} (chạy: npm run build:check)`);
}

const man = MAN_SAU_TAP.find((m) => m.step === "goi-y");
if (!man) throw new Error('không có màn "goi-y" trong MAN_SAU_TAP');

const ten = `__anh-mon-${nhan}.html`;
const trang = path.join(build, ten);
fs.writeFileSync(
  trang,
  trangTuLai(fs.readFileSync(path.join(build, "index.html"), "utf8"), man.kichBan, null),
);

const server = createStaticServer(build);
let browser;
const ketQua = [];
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: RONG, height: CAO, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-lcd-text",
      // Localhost on this machine goes through a proxy that answers 301 for
      // everything, and a probe that measures the proxy's error page looks
      // exactly like a probe that measured a clean screen.
      "--no-proxy-server",
    ],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(120000);
  console.log(`đo trên : ${build}`);
  console.log(`chrome  : ${CHROME}`);

  async function diToiGoiY() {
    await page.goto(`http://127.0.0.1:${port}/${ten}`, { waitUntil: "networkidle0", timeout: 120000 });
    await page.waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), {
      timeout: 120000,
    });
    const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
    if (lai.loi) throw new Error(`đi bộ tới goi-y HỎNG: ${lai.loi}`);
    // Without the needle a measurement of the wrong screen gets reported under
    // the right name.
    const thay = await page.evaluate((n) => (document.body.innerText || "").includes(n), man.needle);
    if (!thay) throw new Error(`đi bộ xong nhưng không thấy "${man.needle}" — đang đo màn khác`);
  }

  /* --- A. where the walk stops: nobody on the bill --- */
  await diToiGoiY();
  ketQua.push(await doMan(page, "A-chua-ai", anhDir, nhan));

  /* --- B. where the demo goes next: three of the group added --- */
  await diToiGoiY();
  for (const nguoi of THEM) {
    const sel = `[aria-label="Thêm ${nguoi} vào nhóm"]`;
    await page.waitForSelector(sel, { visible: true, timeout: 15000 });
    await page.evaluate((s) => document.querySelector(s).click(), sel);
  }
  // 3 dishes x 3 people. A press that silently missed would otherwise leave
  // state A on the glass and get reported under state B's name.
  const oTich = await page.evaluate(() => document.querySelectorAll('[role="checkbox"]').length);
  if (oTich !== MON.length * THEM.length) {
    throw new Error(`mong ${MON.length * THEM.length} ô tích sau khi thêm người, thấy ${oTich}`);
  }
  ketQua.push(await doMan(page, "B-ba-nguoi", anhDir, nhan));

  for (const r of ketQua) inRa(r);
  return ketQua;
} finally {
  if (browser) await browser.close();
  closeServer(server);
  fs.rmSync(trang, { force: true });
}
}

/* ------------------------------------------------------------------ CLI --- */

// Only when run as a script. Imported by the gate, this file must measure
// nothing on its own.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const ketQua = await doMucHangMon();
  console.log(`\nJSON ${JSON.stringify({ build: BUILD, nhan: NHAN, ketQua })}`);
}
