/** Does any snapshot scroll sideways on a 390pt phone?
 *
 * QA found the opening screen scrolling horizontally on the web build. That is
 * a whole class of bug rather than one screen's mistake -- `react-native-web`
 * turns a fixed width or a negative margin into real overflow that nothing on
 * a phone simulator shows -- so it is worth a measurement rather than an
 * opinion, on every screen, every time the snapshots are regenerated.
 *
 * Reads the same `.screen-snapshots/*.html` the detector reads, so it costs no
 * extra build. Reports `scrollWidth` against `clientWidth` at 390 CSS px, and
 * names the widest element when they differ.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && node tools/overflow-check.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const WIDTH = 390;

const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ||
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

function flag(name, fallback) {
  const hit = process.argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : fallback;
}

async function main() {
  const dir = flag("dir", path.join(MOBILE_ROOT, ".screen-snapshots"));
  const files = fs
    .readdirSync(dir)
    .filter((n) => n.endsWith(".html"))
    .sort();
  if (files.length === 0) throw new Error(`no .html in ${dir} — run screen-snapshots.mjs first`);
  if (!fs.existsSync(CHROME)) throw new Error(`Chromium not found at ${CHROME}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: WIDTH, height: 844, deviceScaleFactor: 2, isMobile: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  let bad = 0;
  try {
    const page = await browser.newPage();
    for (const name of files) {
      await page.goto(pathToFileURL(path.join(dir, name)).href, {
        waitUntil: "domcontentloaded",
      });
      const r = await page.evaluate((viewport) => {
        const doc = document.documentElement;
        const over = [];
        for (const el of document.querySelectorAll("*")) {
          const box = el.getBoundingClientRect();
          if (box.width === 0) continue;
          if (box.right > viewport + 0.5 || box.left < -0.5) {
            over.push({
              tag: el.tagName.toLowerCase(),
              cls: (el.getAttribute("class") || "").slice(0, 40),
              left: Math.round(box.left),
              right: Math.round(box.right),
              text: (el.textContent || "").trim().slice(0, 30),
            });
          }
        }
        return {
          scrollWidth: doc.scrollWidth,
          clientWidth: doc.clientWidth,
          bodyScroll: document.body.scrollWidth,
          over: over.slice(0, 5),
          overCount: over.length,
        };
      }, WIDTH);
      const overflows = r.scrollWidth > r.clientWidth;
      if (overflows) bad += 1;
      console.log(
        `${overflows ? "CUON NGANG" : "ok        "} ${name.padEnd(16)} ` +
          `scrollWidth=${r.scrollWidth} clientWidth=${r.clientWidth} ` +
          `body=${r.bodyScroll} phan-tu-tran=${r.overCount}`,
      );
      for (const o of r.over) {
        console.log(`             ${o.tag}.${o.cls} [${o.left}..${o.right}] "${o.text}"`);
      }
    }
  } finally {
    await browser.close();
  }
  // Non-zero when any screen scrolls sideways, so this can gate a run rather
  // than only inform one.
  process.exit(bad === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
