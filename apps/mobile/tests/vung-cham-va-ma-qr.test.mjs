/* One defect on the hero path that only a rendered page can see (bug-191824).
 *
 * There were two. The second -- the VietQR block opening 41% below the fold --
 * went with the payment rail: the product names each person's share and stops,
 * so there is no code to be below any fold. The file keeps its name because
 * four other test files cite it by name as the pattern for measuring a
 * rendered page, and renaming it would cost four edits to buy nothing.
 *
 * QA measured both on main @ 267971e and no existing gate moved, for the same
 * reason as `vo-tab-web.test.mjs`: nothing else in this suite renders anything.
 * `tsc` typechecks props; it does not know react-native-web drops one. The
 * screen-markup tests read emitted HTML; they cannot measure a touch area or a
 * fold.
 *
 *   1. `hitSlop` does nothing on web. `KetQuaNhanDien` drew its delete control
 *      28pt wide and a comment beside it said `hitSlop` "keeps the touch target
 *      at 44". Hit-tested on the web export at 390x844, points 1, 2, 4, 6, 8,
 *      10 and 12px outside the box ALL missed: the real touch area was 28x44,
 *      on the one control on that screen that destroys a row. That clears WCAG
 *      2.2 AA 2.5.8 (24x24) and misses Apple HIG 44 and Android 48dp. Same
 *      class of silent drop as `accessibilityState` never reaching the DOM.
 *
 *   2. The VietQR block opened 41% below the fold. `KetQuaThanhToan` stacked
 *      893pt of content into a 609pt scroller and put the code last, so it
 *      landed at y=728 and 116 of its 196pt were inside a 844pt screen. The
 *      code decoded correctly -- OpenCV read the payload back off a screenshot
 *      -- which is exactly why no other check moved. Decodable is not visible,
 *      and this is the last screen of the demo.
 *
 * Both are measured the way the QA probes measured them, on purpose. #1 asks
 * the page which element a real point belongs to rather than reading a style,
 * because a style that says 44 and a `hitSlop` that says 44 look identical in
 * source and only one of them is true. #2 locates the code block by its own
 * shape -- a near-square div holding 100+ module views, the same locator
 * `anh-bon-man-hero.mjs` uses -- rather than by a test id, so the two cannot
 * disagree about which object they measured.
 *
 * What this file proves: on the build in `MOBILE_WEB_EXPORT`, at 390x844, in
 * this Chrome. What it does not prove: either of them on iOS or Android, where
 * `hitSlop` is real and the safe areas differ. It also does not prove the code
 * is scannable by a bank -- that is `anh-bon-man-hero.mjs` decoding a
 * screenshot, and it is a different question from whether the code is on
 * screen.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/vung-cham-va-ma-qr.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which the `build:check`
 * step of that same command has just written. With no build and no Chrome it
 * skips and says so; `MOBILE_REQUIRE_WEB_A11Y=1` turns that skip into a
 * failure. Same convention as `vo-tab-web.test.mjs`, deliberately.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { MAN_SAU_TAP, trangTuLai } from "../tools/quet-man-sau-tap.mjs";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The phone the demo runs on. Both numbers below are width- and
 *  height-dependent, so this is not a detail that can be generalised away. */
const RONG = 390;
const CAO = 844;

/** Apple HIG and Android's 48dp both sit above this; WCAG 2.2 AA 2.5.8 sits at
 *  24. 44 is the number `KetQuaNhanDien` already claimed in writing. */
const CHAM_TOI_THIEU = 44;

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

/* ------------------------------------------------------ measurements, in-page --- */

/**
 * The touch area of one control, asked rather than read.
 *
 * Walks single pixels outward from the element's centre and keeps the
 * contiguous run of points `elementFromPoint` still resolves to it. That is the
 * only definition that survives `hitSlop` (invisible padding React Native adds
 * and react-native-web does not), an `::before` overlay, and a transparent
 * parent absorbing the press -- all three read as "the box is 28 wide" in
 * source and produce three different answers here.
 *
 * The scan is bounded at 2x the target so a control with no upper limit -- a
 * full-width row, say -- cannot make the loop long.
 */
function doVungCham(prefix, minimum) {
  const nut = [...document.querySelectorAll('[role="button"], button')].filter((e) =>
    (e.getAttribute("aria-label") || "").startsWith(prefix),
  );
  const bien = minimum * 2;
  return nut.map((el) => {
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const trung = (x, y) => {
      const tren = document.elementFromPoint(x, y);
      return !!tren && (tren === el || el.contains(tren));
    };
    const chay = (dx, dy) => {
      let n = 0;
      for (let d = 1; d <= bien; d += 1) {
        if (!trung(cx + dx * d, cy + dy * d)) break;
        n += 1;
      }
      return n;
    };
    return {
      nhan: el.getAttribute("aria-label"),
      hop: { w: Math.round(r.width), h: Math.round(r.height) },
      // +1 for the centre point itself, which every run above excludes.
      cham: {
        w: trung(cx, cy) ? chay(-1, 0) + chay(1, 0) + 1 : 0,
        h: trung(cx, cy) ? chay(0, -1) + chay(0, 1) + 1 : 0,
      },
    };
  });
}


/* -------------------------------------------------------------------- gate --- */

// bug-010019. This gate measures a prebuilt export and opens no source file,
// so an export older than the tree makes it name a control as missing from a
// screen that renders it correctly. Refuse to report rather than report wrong.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`vùng chạm và mã QR — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("vùng chạm và mã QR, đo trên trang render thật", () => {
    let page;
    let server;
    const daTao = [];

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      for (const f of daTao) rmSync(f, { force: true });
    });

    /**
     * Walk the app to one of the screens behind a button, then hand it back.
     *
     * These screens have no fragment: you reach `ket-qua` by pressing [+],
     * then "Tạo khoản chi", then handing the viewfinder a JPEG. `trangTuLai`
     * injects the API stub and the scripted walk ahead of the bundle, which is
     * the same page the QA probes measured -- restating the walk here would
     * let the two drift into describing different apps.
     */
    async function diToi(step) {
      const man = MAN_SAU_TAP.find((m) => m.step === step);
      assert.ok(man, `không có màn "${step}" trong MAN_SAU_TAP`);
      const ten = `__vung-cham-${step}.html`;
      const duong = join(EXPORT_DIR, ten);
      writeFileSync(
        duong,
        trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), man.kichBan, null),
      );
      daTao.push(duong);

      await page.viewport(RONG, CAO);
      await page.goto(server.url + ten);
      // Not `goto`'s own wait: its 15s default is tuned for a page that renders
      // once, and this one presses its way through the whole bill flow first.
      // A timeout here would read as "the screen never rendered".
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 120000,
        label: `kịch bản đi bộ tới "${step}"`,
      });
      const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
      assert.equal(lai.loi, null, `kịch bản đi bộ tới "${step}" HỎNG: ${lai.loi}`);
      assert.equal(lai.xong, true, `kịch bản đi bộ tới "${step}" chưa xong`);

      // The needle is what says the walk landed where it claims. Without it a
      // measurement of the wrong screen reports under the right name -- the
      // failure `quet-man-sau-tap.mjs` documents at length.
      const thay = await page.evaluate(
        (n) => (document.body.innerText || "").includes(n),
        man.needle,
      );
      assert.ok(thay, `đi bộ xong nhưng không thấy "${man.needle}" — đang đo màn khác`);
    }

    /* --- 1. the delete control is 44 wide to a finger, not just in a comment --- */

    test("ba nút Xoá món có vùng chạm thật ít nhất 44x44", async () => {
      await diToi("ket-qua");
      const nut = await page.evaluate(doVungCham, "Xoá món", CHAM_TOI_THIEU);

      // The fixture bill holds three dishes. Asserting the count first is what
      // stops "no buttons found" from passing as "no button is too small".
      assert.equal(
        nut.length,
        3,
        `mong 3 nút Xoá món, thấy ${nut.length}: ${JSON.stringify(nut)}`,
      );

      for (const n of nut) {
        console.log(
          `  "${n.nhan}": hộp ${n.hop.w}x${n.hop.h}, vùng chạm thật ${n.cham.w}x${n.cham.h}`,
        );
      }
      const nho = nut.filter(
        (n) => n.cham.w < CHAM_TOI_THIEU || n.cham.h < CHAM_TOI_THIEU,
      );
      assert.deepEqual(
        nho,
        [],
        `vùng chạm dưới ${CHAM_TOI_THIEU}px (đo bằng elementFromPoint, không đọc style): ` +
          nho
            .map((n) => `"${n.nhan}" ${n.cham.w}x${n.cham.h} (hộp ${n.hop.w}x${n.hop.h})`)
            .join("; "),
      );
    });

  });
}
