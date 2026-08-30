/* Lên plan reaches the trip timeline by pressing a trip, not only by URL.
 *
 * `DongThoiGian` was handed over as "has a file, mentioned in 7 places, so
 * check whether anything leads to it". Both halves of that turned out to need
 * correcting, and the way they were wrong is why this file exists rather than
 * a wiring commit:
 *
 *   - The count conflates three different things. Grepping the string outside
 *     `node_modules` and `dist-test` returns 9 lines in 5 files, and only
 *     **three** of them are this screen: its declaration, and `LenPlan`'s
 *     import and render of it. Three more are `luuDongThoiGian`, the api.ts
 *     function that PUTs a timeline -- a substring match, not the component.
 *     Two are a *separate* local function of the same name declared inside
 *     `screens/ky-niem/KyNiem.tsx`, a different component drawing a finished
 *     trip's stops on the memory wall. The last is `tsconfig.test.json`
 *     listing the file. A name-grep cannot tell three declarations apart, and
 *     the number it returns moves for reasons that have nothing to do with
 *     how reachable the screen is.
 *   - The screen is already reachable. `TheBuoi` in `LenPlan.tsx` is a
 *     `Pressable` carrying `accessibilityLabel="Mở dòng thời gian <tên>"`, and
 *     pressing it swaps the tab over to `DongThoiGian` for that trip. Measured
 *     in Chrome on the real web export, not read off the source.
 *
 * So nothing needed wiring. What was missing is the thing that would notice if
 * the wire were cut, and on 2026-08-31 that was nothing at all: the strings
 * "Mở dòng thời gian", "Thêm chặng" and "Quay lại danh sách" appeared in
 * **zero** files under `tests/` and `tools/`. Measured rather than assumed --
 * replacing `onPress={onMo}` with `onPress={() => {}}` and rebuilding the
 * bundle left the suite at 839 pass / 0 fail, with the trip card dead and the
 * timeline unreachable by any means a person has.
 *
 * Every gate that looks at this screen is blind to that press:
 *
 *   - `tools/tab-snapshots.mjs` drives `#tab=len-plan`, which is the trip
 *     LIST. The timeline is one press further in and the probe never takes it,
 *     so the probe is green with the card dead.
 *   - `tests/moi-man-co-duong-do.test.mjs` enumerates screens `App.tsx`
 *     imports. `DongThoiGian` is mounted by `LenPlan`, not by `App`, so it is
 *     not on that list and its absence is not a red row -- the nested-screen
 *     hole in an otherwise-good gate.
 *   - `tests/buoi-di.test.mjs` and `tests/check-in-chang.test.mjs` do render
 *     `DongThoiGian`, but they construct it directly with props. A component
 *     handed its props renders identically whether or not anything in the app
 *     ever hands them to it.
 *   - Counting files that name `DongThoiGian` returns the same 7 either way.
 *     The press runs through the `onMo` prop, and a name-grep cannot see a
 *     callback.
 *
 * What this proves: from the tab the trip list lives on, a person can press a
 * trip and land on THAT trip's timeline, and get back. What it does NOT prove:
 * that the timeline matches the mockup (it does not -- see below), that saving
 * a stop works (no PUT is exercised here), or that check-in posts (that is
 * `check-in-chang.test.mjs`, on directly-constructed props).
 *
 * ## Pressing the right trip is the assertion worth having
 *
 * "The timeline opened" passes for a hardcoded trip too. The fixture carries
 * two outings on purpose -- one with stops, one with none -- so the second
 * test presses the trip whose timeline is EMPTY and asserts the first trip's
 * stops are absent. That is what separates "a timeline opened" from "this
 * trip's timeline opened", and it is the half a wiring bug survives.
 *
 * ## Known gap this file deliberately does not encode
 *
 * The mockup (`04_outing_management/02_trip_timeline`) groups stops under day
 * headings -- "Ngày 1 · 17/10", "Ngày 2 · 18/10". This screen cannot: a stop's
 * `at` is a wall-clock `HH:MM` on both sides of the wire (`OutingStopInput`
 * pattern on the server, `minute_of_day` 0..1439 in the table), and the "Thêm
 * chặng" form has no day field. The fixture trip spans two days and its stops
 * render as one flat clock-sorted list. No assertion here locks that in as
 * desired -- a test that froze the limitation would be an argument against
 * ever fixing it. It is written up for the Lead instead.
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

/** The two trips in the fixture. The first carries a timeline, the second is
 *  bare -- which is what lets "pressed the right one" be an assertion. */
const CHUYEN_CO_CHANG = "Đà Lạt cuối tuần";
const CHUYEN_RONG = "Cắm trại Tà Năng";

/** The card's accessible name, built in `TheBuoi` from the trip title. */
const nhanThe = (ten) => `Mở dòng thời gian ${ten}`;

/** Text the trip LIST prints and the timeline does not.
 *
 *  Deliberately not the trip title, and not "7 người" or the per-person
 *  budget: the timeline reprints all three, so any of them would pass whether
 *  or not anything navigated. These two are chrome of the list itself -- the
 *  tab's own subtitle, and the other trip's card, which the timeline replaces
 *  rather than scrolls past. */
const CHU_CHI_CO_O_DANH_SACH = ["Chuyến đi của nhóm, ngày giờ và ai đi.", CHUYEN_RONG];

/** Text only the opened timeline prints.
 *
 *  "Số tham chiếu, không phải giới hạn." in full, never the bare "số tham
 *  chiếu": the list card prints "~ 2.500.000đ/người, số tham chiếu" and a
 *  substring check on those three words is green on the list too. */
const CHU_CUA_DONG_THOI_GIAN = [
  "Tổng dự kiến",
  "Số tham chiếu, không phải giới hạn.",
  "Nhãn chặng",
];

/** Stops belonging to the first trip, which only ITS timeline draws. */
const CHANG_CUA_CHUYEN_CO_CHANG = ["09:30", "Cà phê sáng", "19:00", "Ăn tối"];

/** What the timeline says when the trip has no stops yet. */
const CHU_KHI_CHUA_CO_CHANG = "Chưa có chặng nào.";

/** The pinned footer control, outside the scroller on every state. */
const NUT_QUAY_LAI = "Quay lại danh sách";

const TRANG = "__test-duong-vao-dong-thoi-gian.html";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** What is painted, whitespace-normalised. `innerText`, not `textContent`:
 *  the trip cards carry an `aria-label` naming the destination screen, and
 *  counting that as "on screen" would make the negative controls lie -- the
 *  label says "dòng thời gian" while the list is still up. */
function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

/** Accessible names of every trip card on screen. Used to assert the cards are
 *  BUTTONS, which `innerText` cannot tell from a paragraph. */
function nhanCuaMoiThe() {
  return [...document.querySelectorAll('[role="button"], button')]
    .map((e) => e.getAttribute("aria-label"))
    .filter((n) => n && n.startsWith("Mở dòng thời gian"));
}

if (reasons.length && !REQUIRED) {
  test(`đường vào dòng thời gian — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("từ tab Lên plan bấm được vào dòng thời gian của một chuyến", () => {
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

    /** A genuinely fresh mount on the trip list.
     *
     *  The `about:blank` hop is load-bearing: two URLs differing only after
     *  the `#` are one same-document navigation, so React never remounts and
     *  the next test starts on whatever screen the last one left open -- here
     *  a timeline, i.e. the exact state that makes "we reached the timeline"
     *  pass without a press.
     *
     *  The wait is on the SECOND trip's card, not the first. Both arrive in
     *  one `/outings` response, but waiting on the last one drawn is what
     *  says the list finished rather than that it started. */
    async function moDanhSachChuyen() {
      await page.goto("about:blank");
      await page.goto(
        `${server.url}${TRANG}#tab=len-plan&nguoi=${NGUOI}`,
        (t) => document.body.innerText.includes(t),
        CHUYEN_RONG,
      );
    }

    /** Press a trip card and wait for its timeline to be up.
     *
     *  The condition is the "Thêm chặng" form, which is the LAST card in the
     *  scroller, rather than the heading. The heading is the trip title, which
     *  the list card already printed -- so waiting on it would return before
     *  anything navigated and hand the next press a screen still in motion. */
    async function bamVaoChuyen(ten) {
      await page.clickLabel(nhanThe(ten));
      await page.waitFor(
        (a, b) => document.body.innerText.includes(a) && document.body.innerText.includes(b),
        { label: `dòng thời gian của "${ten}" hiện ra` },
        "Nhãn chặng",
        NUT_QUAY_LAI,
      );
    }

    test("tab Lên plan vẽ mỗi chuyến thành một nút bấm được", async () => {
      await moDanhSachChuyen();

      const nhan = await page.evaluate(nhanCuaMoiThe);
      assert.deepEqual(
        nhan.sort(),
        [nhanThe(CHUYEN_RONG), nhanThe(CHUYEN_CO_CHANG)].sort(),
        "mỗi chuyến trong danh sách phải là một nút mang tên đích của nó",
      );

      // And the timeline is not already on screen, which is what makes the
      // "after" half of the next test mean anything.
      const chu = await page.evaluate(chuTrenMan);
      for (const c of CHU_CUA_DONG_THOI_GIAN) {
        assert.ok(!chu.includes(c), `"${c}" không được có sẵn trên danh sách chuyến`);
      }
    });

    test("bấm một chuyến thì mở dòng thời gian của chính chuyến đó", async () => {
      await moDanhSachChuyen();

      const truoc = await page.evaluate(chuTrenMan);
      for (const c of CHU_CHI_CO_O_DANH_SACH) {
        assert.ok(truoc.includes(c), `trước khi bấm phải còn thấy "${c}"`);
      }

      await bamVaoChuyen(CHUYEN_CO_CHANG);

      const sau = await page.evaluate(chuTrenMan);
      for (const c of CHU_CUA_DONG_THOI_GIAN) {
        assert.ok(sau.includes(c), `dòng thời gian phải in "${c}"`);
      }
      // The stops themselves, in clock order on the rail.
      for (const c of CHANG_CUA_CHUYEN_CO_CHANG) {
        assert.ok(sau.includes(c), `dòng thời gian phải in chặng "${c}"`);
      }
      assert.ok(
        sau.indexOf("09:30") < sau.indexOf("19:00"),
        "09:30 phải đứng trước 19:00 trên ray",
      );
      // The half that separates "arrived" from "the tab grew some text".
      for (const c of CHU_CHI_CO_O_DANH_SACH) {
        assert.ok(!sau.includes(c), `dòng thời gian thay cả tab; "${c}" phải biến mất`);
      }
    });

    test("bấm chuyến chưa có chặng thì mở dòng thời gian rỗng của ĐÚNG chuyến đó", async () => {
      await moDanhSachChuyen();
      await bamVaoChuyen(CHUYEN_RONG);

      const sau = await page.evaluate(chuTrenMan);
      assert.ok(
        sau.includes(CHU_KHI_CHUA_CO_CHANG),
        `chuyến chưa có chặng phải nói "${CHU_KHI_CHUA_CO_CHANG}"`,
      );
      assert.ok(sau.includes(CHUYEN_RONG), `màn phải mang tên chuyến "${CHUYEN_RONG}"`);
      // The assertion a hardcoded destination does not survive: the OTHER
      // trip's stops must not be here.
      for (const c of CHANG_CUA_CHUYEN_CO_CHANG) {
        assert.ok(
          !sau.includes(c),
          `chặng "${c}" thuộc "${CHUYEN_CO_CHANG}"; nó không được xuất hiện trên dòng thời gian của "${CHUYEN_RONG}"`,
        );
      }
    });

    test("“Quay lại danh sách” đưa về đúng danh sách chuyến", async () => {
      await moDanhSachChuyen();
      await bamVaoChuyen(CHUYEN_CO_CHANG);

      await page.clickChu(NUT_QUAY_LAI);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "danh sách chuyến hiện lại" },
        CHU_CHI_CO_O_DANH_SACH[0],
      );

      const sau = await page.evaluate(chuTrenMan);
      for (const c of CHU_CHI_CO_O_DANH_SACH) {
        assert.ok(sau.includes(c), `về danh sách rồi thì phải thấy lại "${c}"`);
      }
      for (const c of CHU_CUA_DONG_THOI_GIAN) {
        assert.ok(!sau.includes(c), `rời dòng thời gian rồi thì "${c}" phải biến mất`);
      }
    });
  });
}
