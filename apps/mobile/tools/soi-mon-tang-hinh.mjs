/** Why the three bill items on `goi-y` are in the DOM and not on the glass.
 *
 * Throwaway probe, not a gate. `anh-bon-man-hero.mjs` reported six strings --
 * the three item names and their three prices -- as drawing no pixels, and a
 * screenshot confirms the card renders empty but for its `Giá` header. Before
 * that goes to anybody as a defect it has to be characterised: clipped by an
 * ancestor, painted outside its parent, sized to zero, or covered. Each has a
 * different owner and a different fix, and "invisible" names none of them.
 *
 * Prints, for each item string, its own box and every ancestor's box plus the
 * overflow/height/display that could be doing the clipping.
 *
 *     cd apps/mobile && node tools/soi-mon-tang-hinh.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(path.resolve(HERE, ".."), ".expo-build-check");

const man = MAN_SAU_TAP.find((m) => m.step === "goi-y");
const ten = "__soi-mon.html";
fs.writeFileSync(path.join(BUILD, ten), trangTuLai(fs.readFileSync(path.join(BUILD, "index.html"), "utf8"), man.kichBan, null));

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
  await page.waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), { timeout: 120000 });
  const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
  if (lai.loi) throw new Error(`di bo HONG: ${lai.loi}`);

  const ra = await page.evaluate(() => {
    const canTim = ["Lẩu thái", "280.000", "Nước sâm", "Giá"];
    const out = [];
    for (const t of canTim) {
      let el = null;
      for (const e of document.querySelectorAll("div, span")) {
        if (e.children.length === 0 && (e.textContent ?? "").trim() === t) { el = e; break; }
      }
      if (!el) { out.push({ chu: t, thay: false }); continue; }
      const chuoi = [];
      let cur = el;
      for (let i = 0; i < 7 && cur; i += 1) {
        const r = cur.getBoundingClientRect();
        const st = getComputedStyle(cur);
        chuoi.push({
          the: cur.tagName.toLowerCase() + (cur.className ? `.${String(cur.className).split(" ")[0]}` : ""),
          x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
          overflow: st.overflow, height: st.height, display: st.display,
          flex: `${st.flexGrow}/${st.flexShrink}/${st.flexBasis}`,
          pos: st.position, mau: st.color, nen: st.backgroundColor, opacity: st.opacity,
        });
        cur = cur.parentElement;
      }
      out.push({ chu: t, thay: true, chuoi });
    }
    return out;
  });

  for (const m of ra) {
    console.log(`\n=== "${m.chu}" ${m.thay ? "" : "-- KHONG TIM THAY"}`);
    if (!m.thay) continue;
    for (const [i, c] of m.chuoi.entries()) {
      console.log(
        `  ${i === 0 ? "chu " : `to${i}`}  ${c.the.padEnd(22)} x=${String(c.x).padStart(4)} y=${String(c.y).padStart(5)} ` +
          `w=${String(c.w).padStart(4)} h=${String(c.h).padStart(4)}  of=${c.overflow} H=${c.height} d=${c.display} flex=${c.flex} pos=${c.pos}`,
      );
    }
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
