/**
 * Measure the rendered size of every QR image on the guest page.
 *
 * A squashed QR is the failure this exists to catch. `.qr img` once carried
 * `width: 200px; height: 200px; max-width: 100%`, which shrinks the width on a
 * narrow screen while the height stays pinned -- at a 320px viewport the QR
 * rendered 173x200. A banking app pointed at a non-square QR may simply refuse
 * it, and it would fail at the one moment that matters.
 *
 * No unit test can see this. `assertIn("aspect-ratio", css)` proves a string is
 * in a file, not that the image is square -- exactly the "a green mark is a
 * false claim" pattern this repo keeps warning about. The only honest check
 * lays the page out in a real browser and measures pixels.
 *
 *     python3 -m app.web.preview 8811      # in one shell, from services/api/
 *     node tools/measure_qr.mjs 8811       # in another
 *
 * Deliberately NOT wired into CI: it needs a browser binary, and a check that
 * silently skips when the browser is missing would be worse than no check.
 * It runs on demand, and it is the regression guard named in the QA matrix.
 * Exits non-zero when any QR is not square, so it can gate a release manually.
 */

import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";

const PORT = process.argv[2] || "8811";
const BASE = `http://localhost:${PORT}`;
const STATES = ["one", "two", "limited", "reported", "confirmed"];
const VIEWPORTS = [320, 390, 1440];

/** Resolve playwright from wherever it happens to live on this machine. */
function loadPlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require("playwright");
  } catch {
    // npx leaves usable copies behind; take the first that imports.
    let dirs = [];
    try {
      dirs = execSync("ls -d ~/.npm/_npx/*/node_modules/playwright 2>/dev/null", {
        shell: "/bin/bash",
        encoding: "utf8",
      })
        .split("\n")
        .filter(Boolean);
    } catch {
      /* no npx cache */
    }
    for (const dir of dirs) {
      try {
        return require(dir);
      } catch {
        /* try the next one */
      }
    }
  }
  throw new Error("playwright not found. Run: npm i -D playwright && npx playwright install chromium");
}

/** Playwright's bundled browser revision may not be the one installed here. */
function findChromium() {
  let candidates = [];
  try {
    candidates = execSync("ls -d ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome 2>/dev/null", {
      shell: "/bin/bash",
      encoding: "utf8",
    })
      .split("\n")
      .filter(Boolean);
  } catch {
    /* none installed */
  }
  return candidates.reverse().find(existsSync);
}

const { chromium } = loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch(executablePath ? { executablePath } : {});

const rows = [];
for (const width of VIEWPORTS) {
  for (const state of STATES) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(`${BASE}/?state=${state}`, { waitUntil: "networkidle" });
    // The transfer panel collapses once JS runs; with JS off it is already
    // open. Measuring without opening it reports 0x0 for every QR -- which
    // passes a naive "is it square" check, so open it explicitly.
    await page.evaluate(() =>
      document.querySelectorAll("[data-transfer]").forEach((el) => el.classList.add("is-open")),
    );
    const qrs = await page.$$eval(".qr img", (imgs) =>
      imgs.map((img) => {
        const rect = img.getBoundingClientRect();
        return { w: +rect.width.toFixed(2), h: +rect.height.toFixed(2) };
      }),
    );
    qrs.forEach((qr, index) =>
      rows.push({
        state,
        viewport: width,
        qr: index + 1,
        ...qr,
        square: Math.abs(qr.w - qr.h) < 0.5,
        rendered: qr.w > 0,
      }),
    );
    await page.close();
  }
}
await browser.close();

console.table(rows);

// `rendered` is not decoration: a 0x0 element is "square" by any width-height
// comparison, so a check that only asks about squareness passes on a QR that
// never laid out at all.
const bad = rows.filter((row) => !row.square || !row.rendered);
if (bad.length) {
  console.error(
    `\nFAIL ${bad.length}/${rows.length}: ` +
      bad.map((r) => `${r.state}@${r.viewport} ${r.w}x${r.h}`).join(", "),
  );
  process.exit(1);
}
console.log(`\nOK: ${rows.length}/${rows.length} QR codes square and rendered`);
