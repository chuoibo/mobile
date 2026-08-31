/* The scanner measures ONE width per run, and it is the width it reports.
 *
 * `quet-man-sau-tap.mjs` takes its viewport from `QUET_VIEWPORT`. That value
 * used to reach only the detector subprocess (`imp detect --viewport <v>`),
 * while the browser the file drives itself was opened on a literal
 * `{ width: 390, height: 844 }`. A run at any other width therefore measured
 * two widths at once:
 *
 *   - the detector rendered at the REQUESTED width and produced findings;
 *   - `xetCheChu` then opened its own browser at 390 and adjudicated those
 *     findings -- deciding which were real occlusions and which were scroll
 *     illusions -- against a layout that was never the one they came from.
 *
 * The JSON artifact recorded `viewport: <requested>` for the pair. So the file
 * declared a width it had only half used, and a reader had no way to see it:
 * both halves ran, both produced numbers, and nothing crashed.
 *
 * Measured on the ten hero screens before the fix: a run at 360x800 returned
 * three `text-occlusion` findings on `ket-qua-thanh-toan` against two at 390,
 * and every one of them was dismissed by a browser looking at the 390 layout.
 * Those verdicts may have been correct. They were not measurements.
 *
 * ## What this file asserts on, and why that specific thing
 *
 * The defect was a SECOND, PARALLEL COPY of the width. So a gate that reads the
 * source text near the launch call, or that re-implements the parse and checks
 * the two agree, can pass while the copy drifts again -- that is the same shape
 * of mistake one layer up.
 *
 * `cauHinhTrinhDuyet()` returns the whole `defaultViewport` object, and
 * `puppeteer.launch` is handed its return value verbatim. Asserting on that
 * return value is therefore asserting on the argument the browser is opened
 * with. There is one source, and this reads it.
 *
 * What this proves: the width flowing into the browser follows `QUET_VIEWPORT`,
 * for the default and for an override, and a malformed value stops the run
 * instead of silently falling back. What it does NOT prove: that the detector
 * subprocess and this browser agree -- they read the same `VIEWPORT` const, but
 * that const reaches the subprocess through an argv string this file never
 * sees. Nor does it prove any screen is clean; that is `imp detect` output read
 * by a person, per ADR-0010.
 *
 * The last case opens a real Chrome, because "puppeteer honours
 * defaultViewport" is an assumption and this whole file exists because an
 * assumption about where a number went turned out to be wrong. With no Chrome
 * it skips and says so; `MOBILE_REQUIRE_WEB_A11Y=1` turns that skip into a
 * failure, the same convention `vung-cham-va-ma-qr.test.mjs` uses.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { describe, test } from "node:test";

import { cauHinhTrinhDuyet } from "../tools/quet-man-sau-tap.mjs";
import { CHROME } from "../tools/screen-snapshots.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const TOOL = join(HERE, "..", "tools", "quet-man-sau-tap.mjs");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The phone the demo runs on, and the documented default of the tool. */
const MAC_DINH = { rong: 390, cao: 844 };

/** A narrower real phone. 360x800 is the width the pre-fix run was measured on,
 *  so it is the width that reproduces the original defect. */
const HEP = { rong: 360, cao: 800 };

describe("be ngang cua may quet", () => {
  test("mac dinh van la 390x844 -- ban va la no-op khi khong dat QUET_VIEWPORT", () => {
    const vp = cauHinhTrinhDuyet();
    assert.equal(vp.width, MAC_DINH.rong);
    assert.equal(vp.height, MAC_DINH.cao);
  });

  test("giu nguyen ba thuoc tinh thiet bi -- doi be ngang khong duoc bien no thanh may ban", () => {
    // The pre-fix literal carried these three. A parse that dropped them would
    // change what every rule sees (hover vs touch, 1x vs 2x raster) while the
    // width assertion above still passed.
    const vp = cauHinhTrinhDuyet();
    assert.equal(vp.deviceScaleFactor, 2);
    assert.equal(vp.isMobile, true);
    assert.equal(vp.hasTouch, true);
  });

  test("QUET_VIEWPORT hep hon di THANG vao trinh duyet, khong dung lai o detector", () => {
    const vp = cauHinhTrinhDuyet(`${HEP.rong}x${HEP.cao}`);
    // This is the assertion the bug failed: pre-fix the browser was opened at
    // 390 no matter what this string said.
    assert.equal(vp.width, HEP.rong);
    assert.equal(vp.height, HEP.cao);
    assert.notEqual(vp.width, MAC_DINH.rong);
  });

  test("khoang trang thua van doc duoc -- QUET_VIEWPORT=' 414x896 ' khong pha lo cong", () => {
    const vp = cauHinhTrinhDuyet("  414x896  ");
    assert.equal(vp.width, 414);
    assert.equal(vp.height, 896);
  });

  test("gia tri sai dang thi DUNG lai, khong am tham roi ve 390", () => {
    // Falling back to the default would be the worst outcome available: the run
    // completes, the artifact says one width, the browser used another. That is
    // the defect this file exists for, re-entered through a typo.
    for (const xau of ["390", "390*844", "rongxcao", "", "390x", "x844"]) {
      assert.throws(
        () => cauHinhTrinhDuyet(xau),
        (err) => err instanceof Error && /QUET_VIEWPORT/.test(err.message),
        `"${xau}" phai lam hong luot chay chu khong duoc doc thanh mac dinh`,
      );
    }
  });

  test("mac dinh khong doi doc tu env, nen no la thu trinh duyet thuc su nhan", async () => {
    // `launch` calls `cauHinhTrinhDuyet()` with no argument, so the no-arg path
    // is the one that matters. It closes over a module-level const read from
    // `process.env` at import time -- hence a fresh import under a changed env,
    // not a second call here.
    const truoc = process.env.QUET_VIEWPORT;
    process.env.QUET_VIEWPORT = `${HEP.rong}x${HEP.cao}`;
    try {
      const lai = await import(`${pathToFileURL(TOOL).href}?be-ngang-test=1`);
      const vp = lai.cauHinhTrinhDuyet();
      assert.equal(vp.width, HEP.rong);
      assert.equal(vp.height, HEP.cao);
    } finally {
      if (truoc === undefined) delete process.env.QUET_VIEWPORT;
      else process.env.QUET_VIEWPORT = truoc;
    }
  });
});

describe("trinh duyet that mo dung be ngang do", () => {
  const chrome = process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME;
  const coChrome = !!chrome && existsSync(chrome);

  test("window.innerWidth trong Chrome that khop voi con so da khai", async (t) => {
    if (!coChrome) {
      const ly_do = `khong tim thay Chrome o ${chrome} -- dat PUPPETEER_EXECUTABLE_PATH`;
      // A skip is not a pass. Under the gate flag this is a failure, so a
      // machine with no browser cannot report this file as green.
      if (REQUIRED) assert.fail(ly_do);
      t.skip(ly_do);
      return;
    }

    const { default: puppeteer } = await import("puppeteer-core");
    const vp = cauHinhTrinhDuyet(`${HEP.rong}x${HEP.cao}`);
    const browser = await puppeteer.launch({
      executablePath: chrome,
      headless: true,
      defaultViewport: vp,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    try {
      const page = await browser.newPage();
      // NOT about:blank. Under `isMobile: true` a page with no
      // `<meta name="viewport">` gets Chrome's legacy 980px fallback layout
      // viewport, so `innerWidth` reads 980 whatever width was configured --
      // measured here at 980 !== 360 on the first run of this test. That is a
      // fact about the blank page, not about the config, and asserting on it
      // would have been a false negative. The tool's own pages all emit the
      // meta line below (`trangTuLai`, and the fixture shell), so this is the
      // condition the scanner actually renders under.
      await page.goto(
        "data:text/html," +
          encodeURIComponent(
            '<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><body>do</body>',
          ),
      );
      const do_duoc = await page.evaluate(() => ({
        rong: window.innerWidth,
        cao: window.innerHeight,
        cham: navigator.maxTouchPoints > 0,
      }));
      assert.equal(do_duoc.rong, HEP.rong);
      assert.equal(do_duoc.cao, HEP.cao);
      assert.equal(do_duoc.cham, true);
    } finally {
      await browser.close();
    }
  });
});
