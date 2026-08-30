/** Does `hitSlop` actually enlarge the touch area on react-native-web?
 *
 * Throwaway probe, not a gate. `anh-bon-man-hero.mjs` measured the three delete
 * buttons on `ket-qua` at 28x44, and `KetQuaNhanDien.tsx` says in a comment
 * beside them that `hitSlop` "keeps the touch target at 44". Both can be true
 * at once -- on native. The question is what the WEB build does, because that
 * is what the measurement ran against, and this repo has already been bitten by
 * react-native-web silently dropping a prop (`accessibilityState` -> no
 * `aria-checked`).
 *
 * Asked empirically rather than by reading the library: hit-test real points to
 * the left of the button's box. If `hitSlop` reached the DOM, a point inside the
 * slop returns the button; if it did not, it returns whatever is behind.
 *
 *     cd apps/mobile && node tools/soi-hitslop.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(path.resolve(HERE, ".."), ".expo-build-check");

const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua");
const ten = "__soi-hitslop.html";
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
    const nut = [...document.querySelectorAll('[role="button"], button')].find((e) =>
      (e.getAttribute("aria-label") || "").startsWith("Xoá món"),
    );
    if (!nut) return { thay: false };
    const r = nut.getBoundingClientRect();
    const st = getComputedStyle(nut);
    // Points stepping outward from the left edge. If hitSlop reached the DOM as
    // padding or a pseudo-element, some of these still hit the button.
    const doDuoc = [];
    for (const d of [1, 2, 4, 6, 8, 10, 12]) {
      const x = r.left - d;
      const y = r.top + r.height / 2;
      const top = document.elementFromPoint(x, y);
      doDuoc.push({ cach: d, trung: !!top && (top === nut || nut.contains(top)) });
    }
    return {
      thay: true,
      box: { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 },
      padding: `${st.paddingTop}/${st.paddingRight}/${st.paddingBottom}/${st.paddingLeft}`,
      truoc: getComputedStyle(nut, "::before").content,
      doDuoc,
    };
  });

  if (!ra.thay) {
    console.log("KHONG tim thay nut 'Xoá món' -- man khong dung hoac nhan da doi");
  } else {
    console.log(`nut 'Xoá món':  box = ${ra.box.w} x ${ra.box.h}`);
    console.log(`  padding = ${ra.padding}`);
    console.log(`  ::before content = ${ra.truoc}`);
    console.log("  hit-test sang TRAI ngoai mep box:");
    for (const d of ra.doDuoc) console.log(`    cach ${String(d.cach).padStart(2)}px:  ${d.trung ? "TRUNG nut" : "truot"}`);
    const rong = ra.doDuoc.filter((d) => d.trung).length;
    console.log(
      rong
        ? `\n=> hitSlop CO tac dung tren web: con trung o ${rong}/${ra.doDuoc.length} diem ngoai box`
        : "\n=> hitSlop KHONG tac dung tren web: moi diem ngoai box deu truot, vung cham dung bang box 28px",
    );
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
