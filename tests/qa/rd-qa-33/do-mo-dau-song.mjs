/* Measure the MoDau screen on the LIVE bundle, not on the stripped snapshot.
 *
 * Why this file exists: `imp detect` reports two `clips a positioned child`
 * findings on `.screen-snapshots/mo-dau.html` and on no other screen of the
 * walk. Two readings fit that number equally well and they lead to opposite
 * decisions:
 *
 *   1. the snapshot pipeline invented them -- scripts are stripped, so layout
 *      settles differently than it does in the app, and the repo has already
 *      seen seven such findings that the measurement itself produced;
 *   2. the app really does clip something on the first screen every demo opens
 *      on, and nobody has looked.
 *
 * A stripped HTML file cannot separate the two. This loads the same
 * `expo export` bundle with scripts INTACT, waits for MoDau to render, and
 * asks the live layout engine which positioned children actually overflow a
 * clipping ancestor, by how many pixels, on which sides, and whether any text
 * is inside them. Symmetric overflow with empty text is decorative bleed;
 * one-sided overflow over a text node is a real defect.
 *
 * Read-only. Writes screenshots to /tmp and prints JSON. Nothing in the app
 * imports it, and no QA screenshot enters git (ADR-0010 muc 6.5).
 *
 *     PUPPETEER_EXECUTABLE_PATH=<chromium> \
 *       node tests/qa/rd-qa-33/do-mo-dau-song.mjs [--bundle <dir>] [--out <dir>]
 */
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
}

const REPO = path.resolve(import.meta.dirname, "../../..");
const BUNDLE = path.resolve(
  arg("--bundle", path.join(REPO, "apps/mobile/.expo-build-check")),
);
const OUT = path.resolve(arg("--out", os.tmpdir()));

/** The tagline, not the wordmark: "Ru Di" is also the tab shell header. */
const NEEDLE = "AI đi chơi, chia bill thông minh";

/** Phone first, then the narrowest device the guest page targets. */
const VIEWPORTS = [
  { w: 390, h: 844 },
  { w: 320, h: 568 },
];

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".ttf": "font/ttf",
};

if (!fs.existsSync(path.join(BUNDLE, "index.html"))) {
  console.error(
    `khong thay bundle o ${BUNDLE}\n` +
      `chay truoc: cd apps/mobile && npm run build:check`,
  );
  process.exit(1);
}

const server = http.createServer((req, res) => {
  const asked = decodeURIComponent(req.url.split("?")[0]);
  let file = path.join(BUNDLE, asked === "/" ? "index.html" : asked);
  // Single-page app: unknown paths fall back to the shell rather than 404.
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    file = path.join(BUNDLE, "index.html");
  }
  res.writeHead(200, {
    "Content-Type": MIME[path.extname(file)] || "application/octet-stream",
  });
  res.end(fs.readFileSync(file));
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

const browser = await puppeteer.launch({
  executablePath:
    process.env.PUPPETEER_EXECUTABLE_PATH ||
    "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

/**
 * Every positioned child that overflows a clipping ancestor.
 *
 * Runs in the page. Reports the overflow per side rather than a boolean: the
 * whole question is whether the cut is symmetric decoration or a one-sided
 * loss of content, and a boolean answers neither.
 */
function doCat() {
  const found = [];
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    const clips =
      cs.overflow !== "visible" ||
      cs.overflowX !== "visible" ||
      cs.overflowY !== "visible";
    if (!clips) continue;
    const box = el.getBoundingClientRect();
    for (const child of el.children) {
      const ccs = getComputedStyle(child);
      if (ccs.position !== "absolute" && ccs.position !== "fixed") continue;
      const cbox = child.getBoundingClientRect();
      const sides = {
        trai: Math.round(box.left - cbox.left),
        phai: Math.round(cbox.right - box.right),
        tren: Math.round(box.top - cbox.top),
        duoi: Math.round(cbox.bottom - box.bottom),
      };
      // 1px of rounding is not a clip.
      const cut = Object.fromEntries(
        Object.entries(sides).filter(([, px]) => px > 1),
      );
      if (!Object.keys(cut).length) continue;
      found.push({
        cha: el.tagName.toLowerCase() + [...el.classList].map((c) => "." + c).join(""),
        chaOverflow: `${cs.overflow}/${cs.overflowX}/${cs.overflowY}`,
        con: child.tagName.toLowerCase() + [...child.classList].map((c) => "." + c).join(""),
        // Empty text means nothing readable was lost; this is the field that
        // decides decoration from defect.
        conChu: (child.innerText || "").trim().slice(0, 80),
        conHop: { rong: Math.round(cbox.width), cao: Math.round(cbox.height) },
        biCat: cut,
      });
    }
  }
  return {
    biCat: found,
    caoTrang: document.documentElement.scrollHeight,
    caoCuaSo: innerHeight,
  };
}

const bao = [];
for (const vp of VIEWPORTS) {
  const page = await browser.newPage();
  await page.setViewport({
    width: vp.w,
    height: vp.h,
    deviceScaleFactor: 2,
  });
  await page.goto(`http://127.0.0.1:${port}/`, {
    waitUntil: "networkidle2",
    timeout: 60000,
  });
  await page.waitForFunction(
    (needle) => document.body.innerText.includes(needle),
    { timeout: 30000 },
    NEEDLE,
  );
  // Let the entry animation settle; measuring mid-transition reports a box
  // that never exists at rest.
  await new Promise((resolve) => setTimeout(resolve, 800));

  // `--canary` injects the defect this script is meant to catch: a positioned
  // child carrying text, hanging off one side of a clipping ancestor. A check
  // that has only ever been observed exiting 0 has not been shown to be able
  // to exit 2, and this repo has shipped several of those.
  if (process.argv.includes("--canary")) {
    await page.evaluate(() => {
      const cha = [...document.querySelectorAll("*")].find(
        (el) => getComputedStyle(el).overflow === "hidden" && el.children.length,
      );
      const con = document.createElement("div");
      con.textContent = "CANARY: chu nay bi cat mat mot ben";
      con.style.cssText =
        "position:absolute;left:-140px;top:8px;width:280px;white-space:nowrap;color:#fff";
      cha.appendChild(con);
    });
  }

  const ketQua = await page.evaluate(doCat);
  const anh = path.join(OUT, `rd-qa-33-mo-dau-${vp.w}.png`);
  await page.screenshot({ path: anh });
  bao.push({ khungNhin: `${vp.w}x${vp.h}`, anh, ...ketQua });
  await page.close();
}

await browser.close();
server.close();

console.log(JSON.stringify(bao, null, 1));

// Text inside a clipped positioned child is the case worth failing on; the
// decorative bleed on this screen is symmetric and carries none.
const matChu = bao.flatMap((v) =>
  v.biCat.filter((c) => c.conChu.length > 0).map((c) => ({ ...c, khungNhin: v.khungNhin })),
);
if (matChu.length) {
  console.error(
    `\n${matChu.length} phan tu bi cat CO CHU ben trong:\n` +
      JSON.stringify(matChu, null, 1),
  );
  process.exit(2);
}
console.error("\nkhong co chu nao bi cat tren mo-dau");
