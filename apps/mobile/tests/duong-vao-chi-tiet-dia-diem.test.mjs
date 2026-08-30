/* The place card on Khám phá opens the place detail screen.
 *
 * `ChiTietDiaDiem` is a screen everything said was fine. It has a file, it has
 * a `#dia-diem=` fragment, `tools/tab-snapshots.mjs` scans it, and 806 tests
 * were green. None of that was a statement about the card you press to get
 * there: replacing `onPress={() => onChon(place)}` with `onPress={() => {}}` in
 * `KhamPha.tsx` left the whole suite at 806 pass / 0 fail. The card still
 * renders, still keeps its `button` role, still reads the same to a screen
 * reader -- it just stops going anywhere.
 *
 * That is the failure this file exists to make loud, and it is a different
 * question from the three gates that already look at this screen:
 *
 *   - The URL probe drives `#dia-diem=p-1` directly. It proves the screen can
 *     render; it never touches the card, so it is green with the card dead.
 *   - The detector scans contrast, type and geometry. A `Pressable` wired to
 *     nothing is pixel-identical to one wired correctly.
 *   - Counting how many files name `ChiTietDiaDiem` returns 2 -- an import and
 *     a JSX tag -- whether or not any control reaches it, because the path runs
 *     through a prop callback (`onChon`) and a name-grep cannot see an
 *     indirection.
 *
 * So this asserts the one thing none of them do: press the card a person sees,
 * arrive on the detail screen.
 *
 * ## The stub does not serve `GET /places/{id}`, and that is deliberate here
 *
 * `installTabStubs` answers `/places` and nothing below it, so the second read
 * this screen makes 404s in this harness. The screen is still expected to open
 * fully. That is the design claim in `ChiTietDiaDiem.tsx` -- everything above
 * the fold is drawn from the tapped `Place`, and the detail read only ever ADDS
 * a description and some reviews -- so a server that cannot answer it must cost
 * those two blocks and nothing else. A test that only passed with the detail
 * route up would be a weaker test, not a stronger one.
 *
 * What this proves: the card is a live control and it lands on the right
 * screen, with the detail route down. What it does NOT prove: that the screen
 * is legible, that its contrast passes, or that `GET /places/{id}` is parsed
 * correctly -- those are the detector, `accessibility-testing`, and
 * `nam-man-chi-tiet.test.mjs` respectively.
 */
import assert from "node:assert/strict";
import { existsSync, unlinkSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { API_BASE, NGUOI, installTabStubs, taoFixtures } from "../tools/tab-snapshots.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The card pressed, and a second place used as the negative control.
 *
 *  The detail screen shows exactly one place, so the *other* name disappearing
 *  is what separates "opened the detail screen" from "the list re-rendered".
 *  Both are in the first four, so neither depends on the "Xem tất cả" cap. */
const CHO_BAM = "Tiệm Nướng Xóm Lào";
const CHO_KHAC = "Lẩu Gà Lá É Tao Ngộ";

/** Text only the loaded detail screen prints.
 *
 *  "Khoảng giá" is the price-card heading and "Chỉ đường"/"Lưu địa điểm" are
 *  the bottom bar; the grid prints none of the three. Deliberately NOT the
 *  place name, which is on both screens and would pass without moving, and
 *  deliberately not "Giới thiệu", which needs the detail route this harness
 *  does not serve. */
const CHU_CUA_MAN_CHI_TIET = ["Khoảng giá", "Chỉ đường", "Lưu địa điểm"];

/** The back control's `accessibilityLabel` in `ChiTietDiaDiem.tsx`. */
const NHAN_QUAY_LAI = "Quay lại danh sách";

const TRANG = "__test-duong-vao-chi-tiet.html";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** What is painted, whitespace-normalised. `innerText`, not `textContent`: the
 *  map strip carries place names in an `aria-label` that a person never reads. */
function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

/** The card's full `accessibilityLabel`, read off the DOM rather than rebuilt.
 *
 *  `TheDiaDiem` composes it from the name, the kinds and the distance, and a
 *  copy of that formatting here would be a second spelling free to drift from
 *  the first. Asking the page which button starts with the name keeps one. */
function nhanCuaThe(ten) {
  const el = [...document.querySelectorAll('[role="button"][aria-label]')].find((b) =>
    b.getAttribute("aria-label").startsWith(ten),
  );
  return el ? el.getAttribute("aria-label") : null;
}

if (reasons.length && !REQUIRED) {
  test(`đường vào chi tiết địa điểm — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("thẻ địa điểm ở Khám phá mở được màn chi tiết", () => {
    let page;
    let server;
    const trangPath = join(EXPORT_DIR, TRANG);

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      const indexHtml = readFileSync(join(EXPORT_DIR, "index.html"), "utf8");
      const i = indexHtml.indexOf("<head>");
      assert.ok(i !== -1, "index.html không có <head> để chèn stub");
      const tiem =
        `<script>(${installTabStubs.toString()})(` +
        `${JSON.stringify(API_BASE)},${JSON.stringify(taoFixtures())});</script>`;
      writeFileSync(trangPath, indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6));

      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(390, 844);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      try {
        unlinkSync(trangPath);
      } catch (err) {
        if (err.code !== "ENOENT") throw err;
      }
    });

    /** A genuinely fresh mount on Khám phá.
     *
     *  The `about:blank` hop is load-bearing: navigating between two URLs that
     *  differ only after the `#` is a same-document navigation, so React never
     *  remounts and the second test would start on whatever screen the first
     *  one left open -- which here is the detail screen, i.e. the exact state
     *  that makes "we reached the detail screen" pass without a press. */
    async function moKhamPha() {
      await page.goto("about:blank");
      await page.goto(
        `${server.url}${TRANG}#tab=kham-pha&nguoi=${NGUOI}`,
        (t) => document.body.innerText.includes(t),
        CHO_BAM,
      );
    }

    async function bamVaoThe() {
      const nhan = await page.evaluate(nhanCuaThe, CHO_BAM);
      // A card that is not a button at all fails here, naming that, rather than
      // failing later at "the detail screen never appeared".
      assert.ok(nhan, `không tìm thấy nút nào có aria-label bắt đầu bằng "${CHO_BAM}"`);
      console.log(`  bấm vào: ${nhan}`);
      await page.clickLabel(nhan);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "màn chi tiết hiện ra" },
        CHU_CUA_MAN_CHI_TIET[0],
      );
    }

    test("bấm thẻ địa điểm thì mở màn chi tiết của đúng chỗ đó", async () => {
      await moKhamPha();

      // Before: on the grid, and none of the detail screen's text is up yet.
      // Asserting this first is what stops the test passing on a screen that
      // was already the detail screen.
      const truoc = await page.evaluate(chuTrenMan);
      assert.ok(truoc.includes(CHO_KHAC), `trước khi bấm phải còn thấy "${CHO_KHAC}" trên lưới`);
      for (const chu of CHU_CUA_MAN_CHI_TIET) {
        assert.ok(!truoc.includes(chu), `"${chu}" không được có trên lưới Khám phá`);
      }

      await bamVaoThe();

      const sau = await page.evaluate(chuTrenMan);
      for (const chu of CHU_CUA_MAN_CHI_TIET) {
        assert.ok(sau.includes(chu), `màn chi tiết phải in "${chu}"`);
      }
      assert.ok(sau.includes(CHO_BAM), `màn chi tiết phải là của "${CHO_BAM}"`);
      // The half that separates "opened the detail screen" from "the grid is
      // still there and merely grew some text".
      assert.ok(
        !sau.includes(CHO_KHAC),
        `màn chi tiết chỉ có một chỗ; "${CHO_KHAC}" phải biến mất khỏi màn`,
      );
    });

    test("màn chi tiết vẫn mở đầy đủ khi GET /places/{id} không trả lời", async () => {
      await moKhamPha();
      await bamVaoThe();

      // The stub serves `/places` and nothing under it, so the detail read has
      // already failed by now. Everything drawn from the tapped card must still
      // be here -- that is the whole "the screen is never blank and never
      // waits" claim, measured instead of asserted in a comment.
      const sau = await page.evaluate(chuTrenMan);
      for (const chu of [...CHU_CUA_MAN_CHI_TIET, CHO_BAM, "Đang mở cửa"]) {
        assert.ok(sau.includes(chu), `phải còn "${chu}" dù route chi tiết không trả lời`);
      }
      // And the two blocks that DO need it are absent rather than empty: a
      // heading standing over nothing reads as a load that failed.
      assert.ok(!sau.includes("Giới thiệu"), "không có mô tả thì không được in tiêu đề Giới thiệu");
      assert.ok(
        !sau.includes("Người đi trước nói gì"),
        "không có đánh giá thì không được in tiêu đề Người đi trước nói gì",
      );
    });

    test("nút quay lại đưa về đúng lưới Khám phá", async () => {
      await moKhamPha();
      await bamVaoThe();

      await page.clickLabel(NHAN_QUAY_LAI);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "lưới Khám phá quay lại" },
        CHO_KHAC,
      );

      const sau = await page.evaluate(chuTrenMan);
      assert.ok(sau.includes(CHO_BAM), "quay lại phải thấy lại chỗ vừa xem trên lưới");
      for (const chu of CHU_CUA_MAN_CHI_TIET) {
        assert.ok(!sau.includes(chu), `"${chu}" không được còn sau khi quay lại lưới`);
      }
    });
  });
}
