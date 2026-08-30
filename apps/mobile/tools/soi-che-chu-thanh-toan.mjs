/** Is that `text-occlusion` finding a covered word or a clipped one?
 *
 * Throwaway probe, not a gate. Moving the VietQR block above the two detail
 * cards pushed the last two person rows below the fold of the screen's inner
 * ScrollView, and `imp detect` then reported "Trang" 88% covered and "160.000đ"
 * 100% covered by the footer button. `do-hinh-hoc.mjs` documents exactly this
 * shape: the rule measures raw bounding boxes, so text that has scrolled out of
 * a scroll container still reports as covered by whatever is painted at those
 * coordinates. Believing it would mean moving a layout that is not broken.
 *
 * The two readings differ in one measurable way, so this asks for it:
 *
 *   COVERED  the word is painted at those coordinates and something opaque is
 *            painted on top -- the scroller does not clip, and a person looking
 *            at that spot sees the button instead of the word.
 *   CLIPPED  the word is not painted there at all. Its layout box is under the
 *            button; its ink is not, because the scroller's `overflow` cut it.
 *
 * Printed per word: the box, the nearest scrolling ancestor's clip rect and
 * `overflow`, whether the box is outside that clip, and what `elementFromPoint`
 * returns at the word's own centre.
 *
 *     cd apps/mobile && npm run build:check && node tools/soi-che-chu-thanh-toan.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(path.resolve(HERE, ".."), ".expo-build-check");
const CHU = process.argv.slice(2).length ? process.argv.slice(2) : ["Trang", "160.000đ"];

const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua-thanh-toan");
const ten = "__soi-che-chu-thanh-toan.html";
fs.writeFileSync(
  path.join(BUILD, ten),
  trangTuLai(fs.readFileSync(path.join(BUILD, "index.html"), "utf8"), man.kichBan, null),
);

const server = createStaticServer(BUILD);
let browser;
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-lcd-text"],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(120000);
  await page.goto(`http://127.0.0.1:${port}/${ten}`, { waitUntil: "networkidle0", timeout: 120000 });
  await page.waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), {
    timeout: 120000,
  });
  const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
  if (lai.loi) throw new Error(`di bo HONG: ${lai.loi}`);

  const ra = await page.evaluate((chuCanTim) => {
    const hop = (r) => ({
      top: Math.round(r.top), bottom: Math.round(r.bottom),
      left: Math.round(r.left), right: Math.round(r.right),
    });
    const ten = (el) =>
      el ? `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(" ")[0] : ""}` : "(null)";

    // EVERY match, not the first. "Trang" is both a chip in the sender row and
    // a name in the person list, and the first draft of this probe measured the
    // chip while the detector was talking about the row -- two different
    // elements, one filename, and a conclusion about neither.
    const moi = [];
    for (const chu of chuCanTim) {
      const els = [...document.querySelectorAll("div, span")].filter(
        (e) => e.children.length === 0 && (e.textContent || "").trim() === chu,
      );
      if (els.length === 0) moi.push({ chu, thay: false });
      for (const e of els) moi.push({ chu, el: e });
    }

    return moi.map(({ chu, el, thay }) => {
      if (thay === false) return { chu, thay: false };
      const r = el.getBoundingClientRect();

      let cuon = null;
      for (let p = el.parentElement; p; p = p.parentElement) {
        const st = getComputedStyle(p);
        const co = ["auto", "scroll", "hidden", "clip"];
        if (co.includes(st.overflowY) || co.includes(st.overflowX)) { cuon = { el: p, st }; break; }
      }

      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const tren = document.elementFromPoint(cx, cy);

      // Ink, not layout. A word the scroller clipped leaves the ground colour
      // behind; a word a button covers leaves the button's colour.
      const range = document.createRange();
      range.selectNodeContents(el);
      const veThat = [...range.getClientRects()].some((q) => {
        const el2 = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
        return !!el2 && (el2 === el || el.contains(el2));
      });

      return {
        chu, thay: true,
        box: hop(r),
        cuon: cuon
          ? {
              ten: ten(cuon.el), overflowY: cuon.st.overflowY,
              clip: hop(cuon.el.getBoundingClientRect()),
            }
          : null,
        ngoaiClip: cuon
          ? r.top >= cuon.el.getBoundingClientRect().bottom ||
            r.bottom <= cuon.el.getBoundingClientRect().top
          : null,
        diemGiua: ten(tren),
        veThat,
      };
    });
  }, CHU);

  console.log("== che chu hay cat chu, KetQuaThanhToan 390x844 ==");
  for (const c of ra) {
    if (!c.thay) { console.log(`   "${c.chu}": KHONG TIM THAY`); continue; }
    console.log(`   "${c.chu}"  box top=${c.box.top} bottom=${c.box.bottom}`);
    if (c.cuon) {
      console.log(
        `     vung cuon <${c.cuon.ten}> overflow-y=${c.cuon.overflowY} ` +
          `clip top=${c.cuon.clip.top} bottom=${c.cuon.clip.bottom}`,
      );
      console.log(`     box nam NGOAI clip cua vung cuon: ${c.ngoaiClip ? "CO" : "khong"}`);
    } else {
      console.log("     khong co to tien nao clip");
    }
    console.log(`     elementFromPoint o giua box: ${c.diemGiua}`);
    console.log(
      `     => ${c.veThat ? "CHE CHU THAT: chu co ve o day va bi de len" : "CAT CHU: chu khong duoc ve o toa do do"}`,
    );
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
