/** Measure, on the REAL rendered screens, how reachable the `cha` shortcut is.
 *
 * `che-chu.mjs` clears a finding as `to-cha` whenever ANY element matching the
 * selector the detector named contains the text -- regardless of whether the
 * words are readable (proved by `probe-cha-shortcut.mjs`: 0/5 sample points
 * readable, still cleared).
 *
 * The detector names an occluder by tag + full class list, and
 * `querySelectorAll(".a.b")` matches every element whose class set is a
 * SUPERSET of {a,b}. So an occluder X wrongly clears against text `el` exactly
 * when some ancestor A of `el` has the same tag and a class set containing
 * X's. This walks every (occluder-candidate X, text el) pair on each screen
 * and counts how many land in that state.
 *
 * The output is the share of this app's possible burials that the filter would
 * erase without looking at whether a reader can see the words.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, installTabStubs, moiMan, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.join(HERE, "..");
const BUILD = path.join(MOBILE_ROOT, ".expo-build-check");

const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
const fixtures = taoFixtures();
const tiem =
  `<script>(${installTabStubs.toString()})(` +
  `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
const i = indexHtml.indexOf("<head>");
const trang = indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6);

function doTrang() {
  const la = (el) => el.children.length === 0 && (el.textContent ?? "").trim().length > 0;
  const chu = [...document.querySelectorAll("div,span,p,h1,h2,h3,h4,li,a,button")].filter(la);
  const tatCa = [...document.querySelectorAll("div,span,p,h1,h2,h3,h4,li,a,button")];

  const lop = (el) => {
    const cn = String(el.className ?? "").trim();
    return cn ? new Set(cn.split(/\s+/)) : new Set();
  };
  const conCua = (a, b) => {
    for (const x of a) if (!b.has(x)) return false;
    return true;
  };

  let cap = 0;
  let xoaNham = 0;
  // Elements that would be wrongly cleared against at least one text.
  const keXau = new Set();

  for (const el of chu) {
    // Ancestors of this text, with tag + class set.
    const toTien = [];
    for (let p = el.parentElement; p; p = p.parentElement) {
      toTien.push({ tag: p.tagName, lop: lop(p) });
    }
    for (const x of tatCa) {
      if (x === el || x.contains(el) || el.contains(x)) continue; // not an occluder
      // Only count candidates that could actually bury something: real area
      // and a background that paints. Counting zero-size wrappers would
      // inflate the rate with elements no reader could ever be blocked by.
      const rx = x.getBoundingClientRect();
      if (rx.width < 8 || rx.height < 8) continue;
      const bg = getComputedStyle(x).backgroundColor;
      const m = /^rgba?\(([^)]+)\)$/.exec(bg);
      if (!m) continue;
      const parts = m[1].split(",").map((s) => parseFloat(s));
      if (parts.length > 3 && parts[3] < 0.9) continue; // transparent: not opaque
      cap++;
      const lx = lop(x);
      if (lx.size === 0) continue; // detector prints a bare tag; no class to share
      const nham = toTien.some((a) => a.tag === x.tagName && conCua(lx, a.lop));
      if (nham) {
        xoaNham++;
        keXau.add(x);
      }
    }
  }

  return { soChu: chu.length, soEl: tatCa.length, cap, xoaNham, keXau: keXau.size };
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
    const ten = `__lop-${def.step}.html`;
    const p = path.join(BUILD, ten);
    fs.writeFileSync(p, trang);
    viet.push(p);

    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    await page.goto(`http://127.0.0.1:${port}/${ten}#${def.frag}`, { waitUntil: "networkidle0" });
    await page
      .waitForFunction((n) => (document.body?.innerText ?? "").includes(n), { timeout: 20000 }, def.needle)
      .catch(() => {});
    const r = await page.evaluate(doTrang);
    bang.push({ step: def.step, ...r });
    await page.close();
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  for (const p of viet) fs.rmSync(p, { force: true });
}

console.log("man          chu   el   cap (che,chu)   bi xoa nham      ty le   ke che bi xoa");
let tCap = 0;
let tXoa = 0;
for (const b of bang) {
  tCap += b.cap;
  tXoa += b.xoaNham;
  const ty = b.cap ? ((b.xoaNham / b.cap) * 100).toFixed(1) : "0";
  console.log(
    `${b.step.padEnd(12)}${String(b.soChu).padStart(4)}${String(b.soEl).padStart(5)}` +
      `${String(b.cap).padStart(15)}${String(b.xoaNham).padStart(14)}${(ty + "%").padStart(11)}` +
      `${String(b.keXau).padStart(15)}`,
  );
}
console.log(
  `\nTONG: ${tXoa}/${tCap} cap (che, chu) se bi xoa nham = ${((tXoa / tCap) * 100).toFixed(1)}%`,
);
