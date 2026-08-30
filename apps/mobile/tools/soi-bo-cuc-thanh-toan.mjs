/** Where do the 844 pixels of `KetQuaThanhToan` actually go?
 *
 * Throwaway probe, not a gate. `anh-bon-man-hero.mjs` reported the VietQR block
 * sitting at y=728 with 116 of its 196px inside the viewport, and named it
 * "thuần bố cục". That is a symptom, not an address: a block ends up below the
 * fold because of what is above it, and nothing measured what was above it.
 *
 * So this prints every direct child of the scroller with its height, plus the
 * per-person rows, so a fix can be aimed at the block that is actually spending
 * the space instead of at the one that fell off the bottom.
 *
 *     cd apps/mobile && npm run build:check && node tools/soi-bo-cuc-thanh-toan.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(path.resolve(HERE, ".."), ".expo-build-check");
const CAO = 844;

const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua-thanh-toan");
const ten = "__soi-bo-cuc-thanh-toan.html";
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
    defaultViewport: { width: 390, height: CAO, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
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

  const ra = await page.evaluate((cao) => {
    const chu = (el) => (el.innerText || "").trim().split("\n")[0].slice(0, 40);
    // The vertical scroller is the tallest element whose scrollHeight exceeds
    // its own box; on this screen there is exactly one.
    let cuon = null;
    for (const e of document.querySelectorAll("div")) {
      const r = e.getBoundingClientRect();
      if (r.height < 200) continue;
      if (e.scrollHeight <= e.clientHeight + 4) continue;
      if (!cuon || r.height > cuon.getBoundingClientRect().height) cuon = e;
    }
    if (!cuon) return { thay: false };

    // Expo's ScrollView is a scroller wrapping one content view; the blocks are
    // that view's children.
    const noiDung = cuon.children.length === 1 ? cuon.children[0] : cuon;
    const khoi = [...noiDung.children].map((e) => {
      const r = e.getBoundingClientRect();
      return { chu: chu(e), y: Math.round(r.y), cao: Math.round(r.height) };
    });

    let qr = null;
    for (const e of document.querySelectorAll("div")) {
      const r = e.getBoundingClientRect();
      if (r.width < 80 || r.height < 80) continue;
      if (Math.abs(r.width - r.height) > 12) continue;
      if (e.querySelectorAll("div").length < 100) continue;
      if (!qr || r.width > qr.w) qr = { y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    }
    const hien = qr ? Math.max(0, Math.min(qr.y + qr.h, cao) - Math.max(qr.y, 0)) : 0;

    return {
      thay: true,
      cuon: { y: Math.round(cuon.getBoundingClientRect().y), cao: Math.round(cuon.clientHeight), noiDung: cuon.scrollHeight },
      khoi,
      qr: qr ? { ...qr, hien, tiLe: qr.h ? hien / qr.h : 0 } : null,
    };
  }, CAO);

  if (!ra.thay) throw new Error("khong tim thay vung cuon");
  console.log(`== bo cuc KetQuaThanhToan, 390x${CAO} ==`);
  console.log(`   vung cuon: y=${ra.cuon.y} cao=${ra.cuon.cao}, noi dung ${ra.cuon.noiDung}px`);
  for (const k of ra.khoi) {
    console.log(`   y=${String(k.y).padStart(4)}  cao=${String(k.cao).padStart(4)}  "${k.chu}"`);
  }
  if (ra.qr) {
    console.log(
      `   QR: y=${ra.qr.y} ${ra.qr.w}x${ra.qr.h}, hien ${ra.qr.hien}/${ra.qr.h}px ` +
        `(${Math.round(ra.qr.tiLe * 100)}%)`,
    );
  } else {
    console.log("   QR: khong tim thay");
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
