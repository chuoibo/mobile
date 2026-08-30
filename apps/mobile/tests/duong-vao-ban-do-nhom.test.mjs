/* Khám phá reaches the two map screens by pressing, not only by URL.
 *
 * `DaiBanDo` and `BanDoNhom` were handed over as "has a file, mentioned in 6
 * and 8 places, so probably nothing leads to it". Both halves of that turned
 * out wrong, and the way they were wrong is the reason this file exists rather
 * than a wiring commit:
 *
 *   - `DaiBanDo` is not a destination at all. It is drawn inline on Khám phá
 *     and again inside the search results and the detail screen, so "what
 *     navigates to it" has no answer and never needed one.
 *   - `BanDoNhom` is a destination, and it already had a live button --
 *     "Xem bản đồ của nhóm", `KhamPha.tsx`, gated on `nguoi` exactly as the
 *     screen it opens is.
 *
 * So nothing needed wiring. What was missing is the thing that would notice if
 * the wire were cut, and on 2026-08-31 that was nothing at all: the strings
 * "Xem bản đồ của nhóm" and "Tìm điểm hẹn" appeared in **zero** files under
 * `tests/` and `tools/`. Measured rather than assumed -- replacing
 * `onPress={() => setMoBanDo(true)}` with `onPress={() => {}}` left the suite
 * at 819 pass / 0 fail.
 *
 * Every gate that looks at these screens is blind to that press:
 *
 *   - `tools/tab-snapshots.mjs` drives `#ban-do=1` and `#ban-do=hen` straight
 *     in. Its own header already draws the distinction between "reachable by
 *     URL" and "measured by URL"; this is the third one it does not make --
 *     reachable by a control a person can find. The probe is green with the
 *     button dead, because it never goes near the button.
 *   - `tests/ban-do-nhom.test.mjs` tests the parsers under `ban-do-nhom.ts`.
 *     Pure functions over wire JSON; no screen, no press.
 *   - The detector scans contrast, type and geometry. A `Pressable` wired to
 *     nothing is pixel-identical to one wired correctly.
 *   - Counting files that name `BanDoNhom` returns the same 8 either way. The
 *     press runs through `setMoBanDo`, and a name-grep cannot see a state
 *     setter.
 *
 * What this proves: from the tab the app opens on, a person can press their
 * way to the group map and then to Điểm hẹn, and get back. What it does NOT
 * prove: that `/map`, `/heatmap` or `/areas` are parsed correctly (that is
 * `ban-do-nhom.test.mjs`), that either screen is legible (the detector), or
 * that the counts shown are right (the server owns those).
 *
 * ## The strip is asserted by its caption, not by its dots
 *
 * `DaiBanDo` renders `null` when no place has finite coordinates, so "the
 * strip is on Khám phá" has to be read off something it only prints when it
 * actually drew. The caption is that; the dots are unnamed `View`s on purpose
 * -- see that file's header for why they must not be separately labelled.
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

/** The button under test, `KhamPha.tsx`, and the one below it on `BanDoNhom`. */
const NUT_BAN_DO = "Xem bản đồ của nhóm";
const NUT_DIEM_HEN = "Tìm điểm hẹn";

/** Back controls, which DO carry an `accessibilityLabel` (they draw a glyph). */
const NHAN_VE_KHAM_PHA = "Quay lại Khám phá";

/** A place on the Khám phá grid, used to know the tab has finished loading.
 *
 *  NOT usable as the negative control, which is worth writing down because it
 *  was tried: this is the group's most-visited place, so "Tiệm Nướng Xóm Lào"
 *  is printed by the group map too, under "Đã đi". A control that appears on
 *  both screens passes whether or not anything navigated. In the first four
 *  cards, so it does not depend on "Xem tất cả". */
const CHO_TREN_LUOI = "Tiệm Nướng Xóm Lào";

/** `DaiBanDo`'s caption, minus the count, which moves with the fixture. */
const CHU_CUA_DAI_BAN_DO = "chỗ, từ toạ độ máy chủ gửi. Chưa phải bản đồ thật.";

/** Text Khám phá prints and the group map does not.
 *
 *  The group map replaces the whole tab rather than covering part of it, so
 *  these two disappearing is what separates "arrived on the map" from "the tab
 *  is still here and merely grew some text". Both are chrome of the catalogue
 *  itself -- the grid heading, and `DaiBanDo`'s caption -- rather than any
 *  place name, precisely because the two screens share their place names. */
const CHU_CHI_CO_O_KHAM_PHA = ["Gợi ý cho bạn", CHU_CUA_DAI_BAN_DO];

/** Text only the loaded group map prints.
 *
 *  "Bản đồ nhóm" is its `h1` and proves the screen mounted; "Nhóm hay tụ ở
 *  đâu" is the heatmap heading, the LAST section on the screen, which needs
 *  `/heatmap` to have returned, parsed, and held a district -- so it cannot
 *  paint until everything above it laid out. Neither string is printed by
 *  Khám phá, which is what lets the "before" assertion below be meaningful. */
const CHU_CUA_BAN_DO_NHOM = ["Bản đồ nhóm", "Nhóm hay tụ ở đâu"];

/** The origin picker on Điểm hẹn. Deliberately not its "Điểm hẹn" title:
 *  `Khung` paints a title in the refusal state too, so the title would wave
 *  through exactly the failure worth catching. */
const CHU_CUA_DIEM_HEN = "Ai xuất phát từ đâu";

const TRANG = "__test-duong-vao-ban-do.html";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** What is painted, whitespace-normalised. `innerText`, not `textContent`: the
 *  map strip carries every place name in an `aria-label` a person never reads,
 *  and counting those as "on screen" would make the negative controls lie. */
function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

/** The accessible name of the relative-position strip, or null.
 *
 *  Read off the DOM rather than rebuilt from the fixture: `DaiBanDo` composes
 *  it from the places it actually drew, and a second copy of that formatting
 *  here would be free to drift from the first. */
function nhanCuaDaiBanDo() {
  const el = [...document.querySelectorAll('[role="img"][aria-label]')].find((e) =>
    e.getAttribute("aria-label").startsWith("Sơ đồ vị trí tương đối"),
  );
  return el ? el.getAttribute("aria-label") : null;
}

/** Visible words of every button on screen. Used to assert a control is
 *  ABSENT, where `innerText` alone cannot tell a button from a paragraph. */
function chuCuaMoiNut() {
  return [...document.querySelectorAll('button, [role="button"]')].map((e) =>
    e.textContent.replace(/\s+/g, " ").trim(),
  );
}

if (reasons.length && !REQUIRED) {
  test(`đường vào bản đồ nhóm — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("từ Khám phá bấm được sang bản đồ nhóm và Điểm hẹn", () => {
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
     *  The `about:blank` hop is load-bearing: two URLs differing only after
     *  the `#` are one same-document navigation, so React never remounts and
     *  the next test starts on whatever screen the last one left open --
     *  here the group map, i.e. the exact state that makes "we reached the
     *  group map" pass without a press. */
    async function moKhamPha(fragment = `#tab=kham-pha&nguoi=${NGUOI}`) {
      await page.goto("about:blank");
      await page.goto(
        `${server.url}${TRANG}${fragment}`,
        (t) => document.body.innerText.includes(t),
        CHO_TREN_LUOI,
      );
    }

    /** Press through to the group map, and wait for it to have LOADED.
     *
     *  Waiting on the `h1` alone is not enough, and the difference is not
     *  pedantic: "Bản đồ nhóm" is chrome, painted on the first frame, while
     *  the three reads are still in flight. Measured here, the heatmap card
     *  lands ~200ms later -- so a test that pressed "Tìm điểm hẹn" as soon as
     *  the title appeared measured the button's position, had the card mount
     *  underneath it, and dispatched at coordinates the button had already
     *  left. That is a silent miss, not an error: the press lands on whatever
     *  moved into place, and the failure surfaces later as "Điểm hẹn never
     *  opened", pointing at the product instead of at the wait.
     *
     *  So the condition is the LAST section on the screen. Not a sleep: a
     *  timeout tuned on this machine is a flake on a slower one. */
    async function bamSangBanDoNhom() {
      await page.clickChu(NUT_BAN_DO);
      await page.waitFor(
        (a, b) => document.body.innerText.includes(a) && document.body.innerText.includes(b),
        { label: "bản đồ nhóm hiện ra và tải xong" },
        CHU_CUA_BAN_DO_NHOM[0],
        CHU_CUA_BAN_DO_NHOM[1],
      );
    }

    test("dải bản đồ danh mục được vẽ ngay trên Khám phá", async () => {
      await moKhamPha();

      // `DaiBanDo` is drawn inline, so its "entry" is that Khám phá renders
      // it. Deleting the tag from `KhamPha.tsx` is the mutation this catches;
      // nothing else in the suite would move.
      const chu = await page.evaluate(chuTrenMan);
      assert.ok(
        chu.includes(CHU_CUA_DAI_BAN_DO),
        `Khám phá phải in chú thích của dải bản đồ ("…${CHU_CUA_DAI_BAN_DO}")`,
      );

      // And it drew from real coordinates rather than rendering its empty
      // branch: the accessible name lists the places it actually plotted.
      const nhan = await page.evaluate(nhanCuaDaiBanDo);
      assert.ok(nhan, 'không có phần tử role="img" nào tên "Sơ đồ vị trí tương đối…"');
      assert.ok(
        nhan.includes(CHO_TREN_LUOI),
        `tên của dải bản đồ phải kể cả "${CHO_TREN_LUOI}"; đang là: ${nhan}`,
      );
    });

    test("bấm “Xem bản đồ của nhóm” thì mở màn bản đồ nhóm", async () => {
      await moKhamPha();

      // Before: on the tab, and none of the map screen's text is up yet.
      // Asserting this first is what stops the test passing on a screen that
      // was already the map.
      const truoc = await page.evaluate(chuTrenMan);
      assert.ok(truoc.includes(CHO_TREN_LUOI), `trước khi bấm phải còn thấy "${CHO_TREN_LUOI}"`);
      for (const chu of CHU_CUA_BAN_DO_NHOM) {
        assert.ok(!truoc.includes(chu), `"${chu}" không được có sẵn trên tab Khám phá`);
      }
      assert.ok(
        (await page.evaluate(chuCuaMoiNut)).includes(NUT_BAN_DO),
        `Khám phá phải có nút "${NUT_BAN_DO}"`,
      );

      await bamSangBanDoNhom();

      const sau = await page.evaluate(chuTrenMan);
      for (const chu of CHU_CUA_BAN_DO_NHOM) {
        assert.ok(sau.includes(chu), `màn bản đồ nhóm phải in "${chu}"`);
      }
      // The half that separates "arrived" from "the tab grew some text".
      for (const chu of CHU_CHI_CO_O_KHAM_PHA) {
        assert.ok(!sau.includes(chu), `bản đồ nhóm thay cả tab; "${chu}" phải biến mất khỏi màn`);
      }
    });

    test("từ bản đồ nhóm bấm “Tìm điểm hẹn” thì mở màn Điểm hẹn", async () => {
      await moKhamPha();
      await bamSangBanDoNhom();

      const truoc = await page.evaluate(chuTrenMan);
      assert.ok(
        !truoc.includes(CHU_CUA_DIEM_HEN),
        `"${CHU_CUA_DIEM_HEN}" không được có sẵn trên bản đồ nhóm`,
      );

      await page.clickChu(NUT_DIEM_HEN);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "màn Điểm hẹn hiện ra" },
        CHU_CUA_DIEM_HEN,
      );

      const sau = await page.evaluate(chuTrenMan);
      assert.ok(sau.includes(CHU_CUA_DIEM_HEN), `màn Điểm hẹn phải in "${CHU_CUA_DIEM_HEN}"`);
      assert.ok(
        !sau.includes(CHU_CUA_BAN_DO_NHOM[1]),
        `Điểm hẹn thay cả màn; "${CHU_CUA_BAN_DO_NHOM[1]}" phải biến mất`,
      );
    });

    test("nút quay lại đưa về đúng tab Khám phá", async () => {
      await moKhamPha();
      await bamSangBanDoNhom();

      await page.clickLabel(NHAN_VE_KHAM_PHA);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "tab Khám phá quay lại" },
        CHO_TREN_LUOI,
      );

      const sau = await page.evaluate(chuTrenMan);
      for (const chu of CHU_CUA_BAN_DO_NHOM) {
        assert.ok(!sau.includes(chu), `"${chu}" không được còn sau khi quay lại tab`);
      }
      // Back to the catalogue itself, not merely off the map.
      for (const chu of CHU_CHI_CO_O_KHAM_PHA) {
        assert.ok(sau.includes(chu), `quay lại phải thấy lại "${chu}"`);
      }
      assert.ok(
        (await page.evaluate(chuCuaMoiNut)).includes(NUT_BAN_DO),
        `quay lại phải thấy lại nút "${NUT_BAN_DO}"`,
      );
    });

    /* The gate is a product decision, not an accident, so it is written down.
     *
     * All three group-map routes are member-gated. Opening the screen with no
     * actor would produce a 403 reading "bạn không còn trong nhóm này" to
     * somebody who never identified themselves -- true of the request and
     * misleading about why. `KhamPha.tsx` therefore hides the button and
     * refuses the screen on the same condition, and this holds those two
     * together: dropping the guard from one of the two is the mutation that
     * would otherwise ship a button which opens a refusal. */
    test("chưa nhận người thì không vẽ nút bản đồ nhóm", async () => {
      await moKhamPha("#tab=kham-pha");

      const nut = await page.evaluate(chuCuaMoiNut);
      assert.ok(
        !nut.includes(NUT_BAN_DO),
        `chưa có "nguoi" thì không được vẽ nút "${NUT_BAN_DO}" — nó chỉ mở ra một câu từ chối`,
      );
      // The tab itself is fine without an actor; only the group question is not.
      const chu = await page.evaluate(chuTrenMan);
      assert.ok(chu.includes(CHO_TREN_LUOI), "danh mục vẫn phải xem được khi chưa nhận người");
    });
  });
}
