/* The dish rows on `goi-y` have to reach the glass, in both states of the demo.
 *
 * QA measured this on main @ 7439b1d and filed it as PH-3 of qa-tt-0035, and
 * #342 deferred it on purpose: the scroller's height is not a constant, it is
 * the `flex: 1` leftover of the whole screen, so moving it means deciding how
 * `GoiYChia` divides its canvas rather than editing one number.
 *
 * The measured shape of the defect: at 390x844 the walk lands here with nobody
 * on the bill, and the matrix scroller -- the only flexible block on a screen
 * of five content-sized ones -- held 326pt of content in 164pt. It clipped at
 * y=567. The header word "Giá" sat at y=527 and cleared it; the first dish row
 * sat at y=569 and did not, by two pixels. Nothing else in the card was inside
 * the window, so the screen whose whole job is to show what the AI read off the
 * bill rendered as an empty card with one column heading.
 *
 * Why no existing gate moved on it:
 *
 *   - The rows are in the DOM, at their right sizes, with real text. Anything
 *     reading markup or innerText sees three dishes and passes. `soi-mon-
 *     tang-hinh.mjs` was written to characterise exactly this and prints the
 *     ancestor chain that does the clipping.
 *   - `imp detect` reported 0 findings on this render. Nothing is occluded and
 *     nothing is low contrast; the content simply is not inside its window.
 *   - Text scrolled out of a container is not text covered by an element, and
 *     this repo has burned three times on box arithmetic that conflated them
 *     (`che-chu.mjs`). "Below the fold of a scroller" needs its own question.
 *
 *     An earlier draft of this comment went one step further and said the
 *     occlusion rules "deliberately do NOT fire here". That is measurably
 *     wrong, and it is the kind of wrong that stops the next reader checking.
 *     They fire: on `?man=goi-y-chia` at 390x844 the rule returns three
 *     findings, one of them `"90.000" is 100% covered by an opaque element`,
 *     about dish rows the browser never painted at those coordinates. The rule
 *     compares raw boxes via `elementFromPoint` and has no clip test at all;
 *     put an opaque banner under any overflowing scroller and it accuses one
 *     row per line below the edge. So on this screen occlusion findings are
 *     EXPECTED NOISE, which is worse than silence: a real one would arrive
 *     fourth in a list the reader has learned to wave through.
 *     `che-chu-tren-man-chia-tien.test.mjs` holds that line.
 *
 * So the question this file asks is the one a person answers by looking: is a
 * dish row's own ink box fully inside the scroller's clip box, at first paint,
 * with nothing scrolled. Not "is it in the DOM", not "is it covered".
 *
 * Both states are asserted because the demo passes through both and they fail
 * differently. State A is where the walk stops, nobody on the bill. State B is
 * three people added, which is where a person goes next and where the screen
 * was in fact WORSE: the strip of who-is-on and the wrap of who-is-left were on
 * screen together and the scroller fell to 151pt, putting all three rows under
 * the fold. A gate that only covered state A would have gone green on that.
 *
 * What this proves: on the build in `MOBILE_WEB_EXPORT`, at 390x844, in this
 * Chrome, with this seven-person fixture. What it does not prove: any other
 * viewport, a longer bill, a longer group, iOS or Android safe areas, or that
 * a person understands the screen once they can see it.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/mon-tren-goi-y.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which the `build:check`
 * step of that same command has just written. With no build and no Chrome it
 * skips and says so; `MOBILE_REQUIRE_WEB_A11Y=1` turns that skip into a
 * failure. Same convention as `vung-cham-va-ma-qr.test.mjs`, deliberately.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { MAN_SAU_TAP, trangTuLai } from "../tools/quet-man-sau-tap.mjs";
import { VUNG_CUON_MA_TRAN } from "../dist-test/screens/GoiYChia.js";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The phone the demo runs on. The whole defect is height-dependent, so this
 *  is not a detail that can be generalised away. */
const RONG = 390;
const CAO = 844;

/** The three dishes on the fixture bill, and the three of seven group members
 *  a person adds first. Both lists are asserted for length before anything is
 *  measured: "found no rows" must never read as "no row is hidden". */
const MON = ["Lẩu thái", "Nước sâm", "Cơm rang"];
const THEM = ["Minh", "Trang", "Hải"];

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

/* ------------------------------------------------------ measurement, in-page --- */

/**
 * Each dish row against the clip box of the scroller it lives in.
 *
 * The scroller is found by the nativeID the screen exports, not by class name:
 * react-native-web hashes those and is free to change them. The row is found by
 * its text, taking only leaf nodes, so a container that happens to include the
 * dish name in its subtree cannot stand in for the row itself.
 *
 * "Visible" is the row's own box being fully inside the scroller's box. Partly
 * inside is deliberately not enough: a two-pixel sliver of a 18pt line is what
 * a reader calls invisible, and treating it as a pass is how this defect would
 * come back.
 */
function doHangMon(id, ten) {
  const sc = document.getElementById(id);
  if (!sc) return { co: false };
  const r = sc.getBoundingClientRect();
  const mep = r.y + r.height;
  const hang = [];
  for (const t of ten) {
    let el = null;
    for (const e of document.querySelectorAll("div, span")) {
      if (e.children.length === 0 && (e.textContent ?? "").trim() === t) {
        el = e;
        break;
      }
    }
    if (!el) {
      hang.push({ ten: t, thay: false });
      continue;
    }
    const b = el.getBoundingClientRect();
    hang.push({
      ten: t,
      thay: true,
      y: Math.round(b.y),
      duoi: Math.round(b.bottom),
      lo: b.y >= r.y && b.bottom <= mep,
    });
  }
  return {
    co: true,
    khung: { y: Math.round(r.y), h: Math.round(r.height), mep: Math.round(mep) },
    // How much content the window is holding. Reported rather than asserted:
    // it is the number that says WHY rows fall out, and it is allowed to stay
    // larger than the window -- this screen is meant to scroll.
    noiDung: Math.round(sc.scrollHeight),
    hang,
  };
}

/** Ticks on the matrix. Used to prove the three presses in state B actually
 *  landed before anything is measured: a click that silently missed would
 *  otherwise leave state A on screen and get reported under state B's name. */
function demOTich() {
  return document.querySelectorAll('[role="checkbox"]').length;
}

/* -------------------------------------------------------------------- gate --- */

// bug-010019. This gate measures a prebuilt export and opens no source file,
// so an export older than the tree makes it name a control as missing from a
// screen that renders it correctly. Refuse to report rather than report wrong.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`món trên goi-y — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("món trên màn gợi ý chia, đo trên trang render thật", () => {
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

    /** Same walk the QA probes drive, injected the same way, so this file and
     *  `anh-bon-man-hero.mjs` cannot end up describing two different apps. */
    async function diToiGoiY() {
      const man = MAN_SAU_TAP.find((m) => m.step === "goi-y");
      assert.ok(man, 'không có màn "goi-y" trong MAN_SAU_TAP');
      const ten = "__mon-goi-y.html";
      const duong = join(EXPORT_DIR, ten);
      writeFileSync(
        duong,
        trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), man.kichBan, null),
      );
      daTao.push(duong);

      await page.viewport(RONG, CAO);
      await page.goto(server.url + ten);
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 120000,
        label: 'kịch bản đi bộ tới "goi-y"',
      });
      const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
      assert.equal(lai.loi, null, `kịch bản đi bộ tới "goi-y" HỎNG: ${lai.loi}`);
      assert.equal(lai.xong, true, 'kịch bản đi bộ tới "goi-y" chưa xong');

      // Without the needle, a measurement of the wrong screen reports under the
      // right name -- the failure `quet-man-sau-tap.mjs` documents at length.
      const thay = await page.evaluate(
        (n) => (document.body.innerText || "").includes(n),
        man.needle,
      );
      assert.ok(thay, `đi bộ xong nhưng không thấy "${man.needle}" — đang đo màn khác`);
    }

    /** Assert-and-report in one place so both states print the same table and
     *  a failure carries the geometry that explains it. */
    function chamDiem(nhan, ra) {
      assert.ok(ra.co, `không tìm thấy vùng cuộn ma trận (#${VUNG_CUON_MA_TRAN}) ở ${nhan}`);
      console.log(
        `  [${nhan}] khung cuộn y=${ra.khung.y} h=${ra.khung.h} mép=${ra.khung.mep}, ` +
          `nội dung ${ra.noiDung}pt`,
      );
      for (const h of ra.hang) {
        console.log(
          h.thay
            ? `    ${h.ten.padEnd(10)} y=${h.y}..${h.duoi}  ${h.lo ? "LỘ RA" : "KHUẤT dưới mép"}`
            : `    ${h.ten.padEnd(10)} KHÔNG TÌM THẤY`,
        );
      }

      // Guard first: three dishes have to be on the page at all. Otherwise a
      // fixture that stopped rendering dishes would satisfy "no dish is hidden"
      // and this file would go green on a blank card.
      const mat = ra.hang.filter((h) => !h.thay).map((h) => h.ten);
      assert.deepEqual(mat, [], `không tìm thấy hàng món trên trang ở ${nhan}: ${mat.join(", ")}`);

      const lo = ra.hang.filter((h) => h.lo);
      assert.ok(
        lo.length >= 1,
        `${nhan}: không hàng món nào nằm trọn trong khung cuộn ` +
          `(khung ${ra.khung.y}..${ra.khung.mep}, nội dung ${ra.noiDung}pt) — ` +
          `thẻ trông như rỗng: ${JSON.stringify(ra.hang)}`,
      );
      return lo.length;
    }

    /* --- A. where the walk stops: nobody on the bill yet --- */

    test("chưa ai trên bill: có hàng món nằm trọn trong khung cuộn", async () => {
      await diToiGoiY();
      const ra = await page.evaluate(doHangMon, VUNG_CUON_MA_TRAN, MON);
      const lo = chamDiem("A · chưa ai trên bill", ra);
      console.log(`    => ${lo}/${MON.length} hàng lộ ra`);
    });

    /* --- B. where the demo goes next: three of the group added --- */

    test("thêm 3 người: vẫn có hàng món nằm trọn trong khung cuộn", async () => {
      await diToiGoiY();
      const truoc = await page.evaluate(demOTich);

      for (const ten of THEM) {
        // `clickLabel` dispatches real mouse events and refuses an element that
        // is outside the viewport, so a press that could not have happened on a
        // phone fails here instead of being simulated into working.
        await page.clickLabel(`Thêm ${ten} vào nhóm`);
      }

      const sau = await page.evaluate(demOTich);
      // 3 dishes x 3 people. Asserting the exact number is what stops a press
      // that silently missed from leaving state A on screen under state B's
      // name -- the whole point of measuring this state separately.
      assert.equal(
        sau,
        MON.length * THEM.length,
        `mong ${MON.length * THEM.length} ô tích sau khi thêm ${THEM.length} người, ` +
          `thấy ${sau} (trước khi thêm: ${truoc})`,
      );

      const ra = await page.evaluate(doHangMon, VUNG_CUON_MA_TRAN, MON);
      const lo = chamDiem("B · 3 người trên bill", ra);
      console.log(`    => ${lo}/${MON.length} hàng lộ ra`);
    });
  });
}
