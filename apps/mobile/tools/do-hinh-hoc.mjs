/** Measure the geometry behind a `text-occlusion` finding before believing it.
 *
 * Throwaway probe, not a gate. It exists because this repo has already been
 * burned twice by the same false positive: the rule measures raw bounding
 * boxes, so any text that has scrolled out of a scroll container still reports
 * as "covered" by whatever is painted at those coordinates -- usually a pinned
 * button or the tab bar. Fixing a layout that is not broken is how a real
 * regression gets introduced, so the boxes get printed before anything moves.
 *
 *     node tools/do-hinh-hoc.mjs ban-be "Phạm Hoàng Anh Thư"
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, installTabStubs, moiMan, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(HERE, "..", ".expo-build-check");

const step = process.argv[2];
const chuCanTim = process.argv[3];
const man = moiMan().find((m) => m.step === step);
if (!man) throw new Error(`khong co man "${step}"`);

const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
const fixtures = taoFixtures();
const tiem =
  `<script>(${installTabStubs.toString()})(` +
  `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
const i = indexHtml.indexOf("<head>");
const trang = indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6);
const ten = `__do-${step}.html`;
fs.writeFileSync(path.join(BUILD, ten), trang);

const server = createStaticServer(BUILD);
let browser = null;
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/${ten}#${man.frag}`, { waitUntil: "networkidle0" });
  await page.waitForFunction(
    (n) => document.body.innerText.includes(n),
    { timeout: 15000 },
    man.needle,
  );

  const ket = await page.evaluate((chu) => {
    const hop = (el) => {
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right) };
    };
    // The deepest element whose own text is the string, so we measure the text
    // run rather than a card that happens to contain it.
    const els = [...document.querySelectorAll("div,span")].filter(
      (e) => e.textContent.trim() === chu && e.children.length === 0,
    );
    const cuon = [...document.querySelectorAll("*")].filter((e) => {
      const s = getComputedStyle(e);
      return /auto|scroll/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 4;
    });
    return {
      viewport: { w: innerWidth, h: innerHeight },
      chu: els.map(hop),
      khungCuon: cuon.map((e) => ({ ...hop(e), scrollHeight: e.scrollHeight, clientHeight: e.clientHeight })),
      nut: [...document.querySelectorAll("button")].map((e) => ({ nhan: e.innerText.trim().slice(0, 24), ...hop(e) })),
    };
  }, chuCanTim);

  console.log(JSON.stringify(ket, null, 2));
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
