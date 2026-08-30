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
 * Three different build numbers were frozen across the tree -- 1187, 1194,
 * 1234. Nobody chose three; three is what you get when the answer is copied
 * from whatever `ls` printed that week. On any other machine all three are
 * wrong, and on this one two of them are stale.
 *
 * ## The search itself is NOT implemented here
 *
 * `findChrome()` in apps/mobile/tests/chrome-cdp.mjs already searches the
 * Playwright cache under the current user's home, newest build first, then five
 * system locations. #329 chose to reuse it rather than reimplement it, in those
 * words: "a second copy of that search would be a second thing to keep
 * correct." An earlier draft of this file was that second copy. It is now a
 * wrapper, and the import is a relative path inside the repository -- which
 * travels -- not a path inside a home directory, which does not.
 *
 * ## What this adds, and why it is not just a re-export
 *
 * `findChrome()` returns null, and apps/mobile's CHROME falls back to the
 * string "/usr/bin/google-chrome". For a tool that skips when there is no
 * browser, that is fine. For QA evidence it is the wrong failure: that path
 * does not exist on the machine that wrote every verdict in this repository, so
 * the fallback hands puppeteer a file that is not there and the probe dies
 * somewhere deep in a launch routine, or worse, gets skipped and reported as a
 * clean run. A skipped probe reported as green is the failure mode this
 * repository has been bitten by most.
 *
 * So this throws, and the message says where it looked.
 */
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import { findChrome } from "../../apps/mobile/tests/chrome-cdp.mjs";

/**
 * Absolute path to a Chromium-family binary on THIS machine.
 *
 * Order: PUPPETEER_EXECUTABLE_PATH, then whatever findChrome() finds (which
 * consults CHROME_BIN first, then the Playwright cache, then system names).
 * Throws if there is none. Callers pass the result to `executablePath`.
 */
export function timTrinhDuyet() {
  const pinned = process.env.PUPPETEER_EXECUTABLE_PATH;
  if (pinned) {
    // An override that is set but wrong is a mistake worth naming, not worth
    // silently falling through: the caller believes they chose the browser.
    if (!existsSync(pinned)) {
      throw new Error(
        `PUPPETEER_EXECUTABLE_PATH=${pinned} nhung file do khong ton tai`,
      );
    }
    return pinned;
  }

  const found = findChrome();
  if (found) return found;

  const chromeBin = process.env.CHROME_BIN;
  if (chromeBin) {
    // findChrome() returns null outright when CHROME_BIN is set and missing --
    // it never falls through to the cache -- so say which of the two happened.
    throw new Error(`CHROME_BIN=${chromeBin} nhung file do khong ton tai`);
  }

  throw new Error(
    "Khong tim thay Chromium. Da tim trong " +
      join(homedir(), ".cache", "ms-playwright") +
      " va cac vi tri he thong (/usr/bin/google-chrome, ...).\n" +
      "Dat PUPPETEER_EXECUTABLE_PATH, hoac: npx playwright install chromium",
  );
}
