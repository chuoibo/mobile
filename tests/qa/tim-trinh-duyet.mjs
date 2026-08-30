/* Where is the browser? Asked once, for every QA probe under tests/qa.
 *
 * Nine scripts here used to answer it by pasting the path that happened to work
 * the day they were written:
 *
 *     const CHROME = process.env.PUPPETEER_EXECUTABLE_PATH ??
 *       "/home/<user>/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";
 *
 * (written with <user> on purpose: the gate that keeps this file honest reads
 * comments too, because run instructions live in comments)
 *
 * Three different build numbers are frozen across the tree -- 1187, 1194, 1234.
 * Nobody chose three; three is what you get when the answer is copied from
 * whatever `ls` printed that week. On any other machine all three are wrong, and
 * on this one two of them are stale.
 *
 * The order below is deliberate. An explicit env var wins, because a human who
 * sets it has a reason. Then the Playwright cache, newest build first, because
 * that is where this machine actually keeps browsers and a scan cannot go stale
 * the way a pasted path does. Then the system locations, because that is where
 * CI and most other Linux boxes keep them.
 *
 * `/usr/bin/google-chrome` alone is NOT a sufficient default, which is worth
 * writing down: it does not exist on the machine that wrote every verdict in
 * this repository. A default that is wrong here would have quietly moved the
 * breakage rather than removed it.
 *
 * This mirrors `findChrome()` in apps/mobile/tests/chrome-cdp.mjs, with one
 * deliberate difference: that one returns null and lets its callers skip. A
 * skipped QA probe is the failure mode this repository has been bitten by most
 * -- a green that measured nothing -- so this one throws, and the message names
 * every place it looked.
 */
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const SYSTEM_NAMES = [
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/snap/bin/chromium",
];

/** Build number from a directory like `chromium-1194`, for newest-first sort. */
function soBanDung(dir) {
  const m = /-(\d+)$/.exec(dir);
  return m ? Number(m[1]) : 0;
}

function quetCachePlaywright(daTim) {
  const cache = join(homedir(), ".cache", "ms-playwright");
  daTim.push(cache);
  if (!existsSync(cache)) return null;

  const dirs = readdirSync(cache)
    .filter((d) => d.startsWith("chromium"))
    .sort((a, b) => soBanDung(b) - soBanDung(a));

  for (const dir of dirs) {
    for (const rel of [
      ["chrome-linux", "chrome"],
      ["chrome-linux64", "chrome"],
      ["chrome-linux", "headless_shell"],
      ["chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"],
    ]) {
      const bin = join(cache, dir, ...rel);
      if (existsSync(bin)) return bin;
    }
  }
  return null;
}

/**
 * Absolute path to a Chromium-family binary on THIS machine.
 *
 * Throws with the full search list if there is none. Callers pass the result
 * straight to `executablePath`.
 */
export function timTrinhDuyet() {
  const daTim = [];

  for (const bien of ["PUPPETEER_EXECUTABLE_PATH", "CHROME_BIN"]) {
    const v = process.env[bien];
    if (!v) continue;
    // An env var that is set but wrong is a mistake worth naming, not worth
    // silently falling through: the caller believes they chose the browser.
    if (!existsSync(v)) {
      throw new Error(`${bien}=${v} nhung file do khong ton tai`);
    }
    return v;
  }

  const tuCache = quetCachePlaywright(daTim);
  if (tuCache) return tuCache;

  for (const bin of SYSTEM_NAMES) {
    daTim.push(bin);
    if (existsSync(bin)) return bin;
  }

  throw new Error(
    "Khong tim thay Chromium. Da tim:\n" +
      daTim.map((p) => `  ${p}`).join("\n") +
      "\nDat PUPPETEER_EXECUTABLE_PATH, hoac: npx playwright install chromium",
  );
}
