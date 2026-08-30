/* The Khám phá grid cuts at four, and "Xem tất cả" is what uncuts it.
 *
 * Measured on a real render, not on the source, because both halves of this
 * are state: the cap is a `slice` over sorted data and the link is a `useState`
 * toggle, and `renderToStaticMarkup` can express neither. A source-reading gate
 * here would assert that the word "slice" appears in a file, which is the
 * shape of check this project has been burned by more than once -- the copy
 * stays put while the behaviour walks away.
 *
 * ## What this covers that the detector scan does not
 *
 * `tools/quet-tab-url.mjs` scans both states and reports zero anti-patterns in
 * each. That is a statement about contrast, type and geometry. It is NOT a
 * statement that the cap works: delete the `slice` and the collapsed screen
 * renders six perfectly well-formed cards, and the scan still says zero. It is
 * not a statement that the link works either -- a `Pressable` wired to nothing
 * is visually identical to one wired to the toggle.
 *
 * So the two gates answer different questions and neither substitutes for the
 * other. This file answers "does the control do what its label says".
 *
 * ## Why the assertions are about NAMES rather than card counts
 *
 * Counting cards means counting DOM nodes matching some class or role, and
 * react-native-web hands out shared atomic classes that make any such selector
 * a superset of what it looks like it selects. Names are what a person reads,
 * they are unambiguous, and they carry the ordering too: the fixture is sorted
 * by `byMatchThenRating`, so *which* four survive the cut is itself a claim.
 *
 * `Cà Phê Vợt Hẻm 330` is the fifth in that order and the needle throughout. It
 * is also the row with `match: null`, so it doubles as the check that a place
 * the model never scored shows no percentage -- the rule `places.ts` calls the
 * exact spot where a demo starts lying politely.
 */
import assert from "node:assert/strict";
import { existsSync, unlinkSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { API_BASE, NGUOI, installTabStubs, taoFixtures } from "../tools/tab-snapshots.mjs";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The six fixture places in the order `byMatchThenRating` puts them.
 *
 *  Open places first by score (95, 88, 74, 69), then the one with no model
 *  answer, then the shut one last regardless of anything else. Written out
 *  rather than derived so that a change to the sort has to change this list
 *  too, deliberately, instead of the list quietly agreeing with whatever the
 *  code now does. */
const THEO_THU_TU = [
  "Tiệm Nướng Xóm Lào",
  "Lẩu Gà Lá É Tao Ngộ",
  "Chill Đêm Đà Lạt",
  "Khu vui chơi DREAMpark",
  "Cà Phê Vợt Hẻm 330",
  "Nướng Ngói Trời Thông",
];

/** Must match `SO_THE_MAC_DINH` in `KhamPha.tsx`. */
const CAT_TAI = 4;

const TRUOC_KHI_BAM = THEO_THU_TU.slice(0, CAT_TAI);
const SAU_KHI_BAM = THEO_THU_TU.slice(CAT_TAI);

const NHAN_MO = `Xem tất cả (${THEO_THU_TU.length})`;
const NHAN_DONG = "Thu gọn";

/** A scan page: the API stub ahead of the bundle, same trick and same fixtures
 *  as `tools/quet-tab-url.mjs`, so the screen tested here and the screen
 *  scanned there cannot be two different screens. */
const TRANG = "__test-luoi-kham-pha.html";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** Which of the six names are on screen, in the order they appear.
 *
 *  `innerText`, not `textContent`: the map strip carries every place name in
 *  its `aria-label` so it can be announced as one diagram, and `textContent`
 *  would not see that either -- but `innerText` is the honest "what is painted"
 *  reading and it is the one worth pinning. */
function tenDangHien(ten) {
  const chu = document.body.innerText.replace(/\s+/g, " ");
  return ten.filter((t) => chu.includes(t));
}

/** Every percentage painted on the screen. The badge is the only thing on this
 *  screen that renders one, so this counts match badges that show a number. */
function phanTramTrenMan() {
  return (document.body.innerText.match(/\d+%/g) ?? []).sort();
}

// bug-010019. This gate measures a prebuilt export and opens no source file,
// so an export older than the tree makes it name a control as missing from a
// screen that renders it correctly. Refuse to report rather than report wrong.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`lưới Khám phá trên web — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("lưới Khám phá cắt ở bốn, Xem tất cả mở phần còn lại", () => {
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

    /** Land on Khám phá with the catalogue loaded, from a genuinely fresh mount.
     *
     *  The `about:blank` hop is load-bearing, not tidiness. Navigating to a URL
     *  that differs from the current one only after the `#` is a same-document
     *  navigation: Chrome fires no load, React never remounts, and the screen
     *  keeps whatever state the previous test left on it. Without this hop the
     *  third test opened an already-expanded grid, found no "Xem tất cả" to
     *  press, and failed while the code under it was correct -- and the far
     *  worse version of that bug is the one where a stale expanded grid makes a
     *  later assertion pass for the wrong reason.
     *
     *  Waiting on the first place name rather than on the heading: the heading
     *  is chrome and paints in the error state too, so it would wave through a
     *  screen that never got data. */
    async function moKhamPha() {
      await page.goto("about:blank");
      await page.goto(
        `${server.url}${TRANG}#tab=kham-pha&nguoi=${NGUOI}`,
        (t) => document.body.innerText.includes(t),
        THEO_THU_TU[0],
      );
    }

    test("mới vào: đúng bốn chỗ đầu, hai chỗ cuối chưa vẽ", async () => {
      await moKhamPha();
      const hien = await page.evaluate(tenDangHien, THEO_THU_TU);
      console.log(`  đang hiện: ${hien.join(" | ")}`);
      assert.deepEqual(
        hien,
        TRUOC_KHI_BAM,
        "lưới thu gọn phải vẽ đúng bốn chỗ đầu theo thứ tự đã sắp",
      );
      // The negative half, said separately so a failure names which side broke.
      for (const t of SAU_KHI_BAM) {
        assert.ok(!hien.includes(t), `"${t}" không được vẽ khi lưới còn thu gọn`);
      }
    });

    test("bấm Xem tất cả: đủ sáu chỗ, nhãn đổi thành Thu gọn", async () => {
      await moKhamPha();
      await page.clickLabel(NHAN_MO);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: `chỗ thứ ${CAT_TAI + 1} hiện ra` },
        SAU_KHI_BAM[0],
      );

      const hien = await page.evaluate(tenDangHien, THEO_THU_TU);
      console.log(`  sau khi bấm: ${hien.join(" | ")}`);
      assert.deepEqual(hien, THEO_THU_TU, "mở rộng phải vẽ đủ sáu chỗ, đúng thứ tự");

      const chu = await page.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
      assert.ok(chu.includes(NHAN_DONG), `nhãn phải đổi thành "${NHAN_DONG}" sau khi mở`);
      assert.ok(!chu.includes(NHAN_MO), `nhãn "${NHAN_MO}" không được còn sau khi đã mở`);
    });

    test("bấm Thu gọn: quay lại đúng bốn chỗ", async () => {
      await moKhamPha();
      await page.clickLabel(NHAN_MO);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "mở rộng xong" },
        SAU_KHI_BAM[0],
      );
      await page.clickLabel(NHAN_DONG);
      await page.waitFor(
        (t) => !document.body.innerText.includes(t),
        { label: "thu gọn xong" },
        SAU_KHI_BAM[0],
      );

      const hien = await page.evaluate(tenDangHien, THEO_THU_TU);
      assert.deepEqual(hien, TRUOC_KHI_BAM, "thu gọn phải quay lại đúng bốn chỗ đầu");
    });

    /* Chỗ máy chủ không chấm thì không có phần trăm nào được vẽ ra.
     *
     * Đây là luật của rd-be-05, và nó chỉ kiểm được ở trạng thái mở rộng: chỗ
     * `match: null` đứng thứ năm nên lưới thu gọn không vẽ nó, và một phép đo
     * trên màn thu gọn sẽ xanh mà chưa từng gặp ca cần gác. */
    test("mở rộng: chỉ bốn chỗ AI chấm mới có phần trăm, hai chỗ kia không bịa số", async () => {
      await moKhamPha();
      await page.clickLabel(NHAN_MO);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "mở rộng xong" },
        SAU_KHI_BAM[0],
      );

      const pt = await page.evaluate(phanTramTrenMan);
      console.log(`  phần trăm trên màn: ${pt.join(", ") || "(không có)"}`);
      assert.deepEqual(
        pt,
        ["69%", "74%", "88%", "95%"].sort(),
        "đúng bốn chỗ có verdict của model mới được hiện phần trăm",
      );
    });
  });
}
