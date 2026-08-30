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
 *
 * ## 2026-08-31: this file made main red at random, and why
 *
 * On 2026-08-30 a full `gate_merge` for #370 -- a documentation-only pull
 * request, not one line of product code -- came back 842 tests / 835 pass /
 * 7 FAIL, all of them here, all of them
 * `timed out waiting for bản đồ nhóm hiện ra và tải xong`. Cases 2, 3 and 4
 * failed; 1 and 5 passed. It was read as "the mobile stage is flaky", which
 * is the reading that costs the most: a good pull request eats a FAIL and its
 * author goes hunting a bug that does not exist. With Actions down for
 * billing, `gate_merge` is the only gate deciding merges, so a lying stage
 * here is a lying gate everywhere.
 *
 * The cause was in the waiting, not in the app or in the machine. One
 * condition -- `"Bản đồ nhóm"` AND `"Nhóm hay tụ ở đâu"` -- was standing in
 * for three different claims: that the press landed, that the screen mounted,
 * and that `/heatmap` answered with at least one district. The first two are
 * guaranteed; the third is not, and `BanDoNhom` does not retry a read that
 * refused. So a single bad answer from `/heatmap` turns that wait from slow
 * into UNSATISFIABLE -- it burns the whole timeout and then names the button.
 * Three cases stood on that one condition, which is why one hiccup reddened
 * three of them.
 *
 * What the repair is, and what it is not: the timeout is unchanged at 15s.
 * Raising it would have hidden the symptom and kept the lie. Instead the
 * claims are separated -- navigation cases wait on chrome only, one case owns
 * the screen-loads claim -- the press-safety wait became a condition (the
 * control has stopped moving) instead of a proxy for it, and every wait in
 * this file now prints the screen and the stub's request log when it runs
 * out, so the next red says which of the three broke.
 *
 * Measured while repairing, and worth keeping because it narrows the next
 * search: the press itself is NOT the flake. 100 presses of
 * "Xem bản đồ của nhóm" under 14-way CPU load landed 100 times, and the
 * button's position is stable to the pixel across 2s. What does redden under
 * load is `moKhamPha` -- 16 copies of this file at once produced 3 timeouts
 * there in 16 runs, which is honest slowness and now says so.
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
 *  Khám phá, which is what lets the "before" assertion below be meaningful.
 *
 *  The two are NOT interchangeable, and treating them as one condition is
 *  what made this file flicker on main -- see `bamSangBanDoNhom`. */
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

/** Where a control sits, as a string, or null when it is not on screen yet.
 *
 *  A string rather than a box so "did it move" is one `===` in the polling
 *  loop below; nothing here needs the numbers themselves. */
function viTriCuaNut(kieu, khoa) {
  const els =
    kieu === "nhan"
      ? [...document.querySelectorAll("[aria-label]")].filter(
          (e) => e.getAttribute("aria-label") === khoa,
        )
      : [...document.querySelectorAll('button, [role="button"]')].filter(
          (e) => e.textContent.replace(/\s+/g, " ").trim() === khoa,
        );
  if (els.length !== 1) return null;
  const r = els[0].getBoundingClientRect();
  return `${Math.round(r.top)}x${Math.round(r.left)}`;
}

/** The stub's request log, for the failure messages below. */
function nhatKyGoi() {
  return (window.__snapshotApiLog ?? []).join(" | ");
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
      // The needle is waited for HERE rather than handed to `goto`, so that a
      // tab which never finishes rendering says so with the screen attached.
      // `goto`'s own label is "trang render xong", which on a loaded machine
      // is indistinguishable from a blank page and from a stub that failed to
      // install. Measured: 16 copies of this file at once reddens exactly this
      // wait, 3 runs in 16.
      await page.goto(`${server.url}${TRANG}${fragment}`);
      await doi(
        (t) => document.body.innerText.includes(t),
        `tab Khám phá render xong (${fragment})`,
        CHO_TREN_LUOI,
      );
    }

    /** Wait, and say what was on screen if the wait ran out.
     *
     *  `waitFor` alone throws "timed out waiting for <label>" and nothing
     *  else, and that message cost a lane a whole turn on 2026-08-30: a run
     *  of this file on a loaded machine reported "bản đồ nhóm hiện ra và tải
     *  xong" three times, and from that sentence there was no way to tell
     *  whether the press had missed, a read had refused, or the box was just
     *  slow. Those need three different fixes. The screen text and the stub's
     *  request log separate them in one read. */
    async function doi(fn, nhan, ...args) {
      try {
        await page.waitFor(fn, { label: nhan }, ...args);
      } catch (err) {
        const chu = await page.evaluate(chuTrenMan).catch(() => "(không đọc được màn)");
        const goi = await page.evaluate(nhatKyGoi).catch(() => "(không đọc được nhật ký)");
        err.message += `\n    màn đang là: ${chu.slice(0, 500)}\n    đã gọi: ${goi}`;
        throw err;
      }
    }

    /** Hold until a control is on screen AND has stopped moving.
     *
     *  This is the wait that makes the next press safe, and it is a condition
     *  rather than a clock: two consecutive polls at the same offset. The
     *  hazard is real and was measured -- the heatmap card mounts under the
     *  group map's buttons, so a press measured before it lands dispatches at
     *  coordinates the button has already left. That is a SILENT miss: the
     *  click hits whatever moved into place and the failure surfaces later as
     *  "Điểm hẹn never opened", pointing at the product instead of at us. */
    async function choNutYen(kieu, khoa) {
      const han = Date.now() + 15000;
      let truoc = null;
      let yen = 0;
      for (;;) {
        const vi = await page.evaluate(viTriCuaNut, kieu, khoa).catch(() => null);
        if (vi !== null && vi === truoc) {
          if (++yen >= 2) return;
        } else {
          yen = 0;
        }
        truoc = vi;
        if (Date.now() > han) {
          const chu = await page.evaluate(chuTrenMan).catch(() => "(không đọc được màn)");
          throw new Error(
            `"${khoa}" không đứng yên (hoặc không có) sau 15s; vị trí cuối ${vi}\n` +
              `    màn đang là: ${chu.slice(0, 500)}`,
          );
        }
        await new Promise((r) => setTimeout(r, 60));
      }
    }

    /** Press through to the group map, and wait until it can be pressed on.
     *
     *  What this deliberately does NOT wait for is the heatmap heading, and
     *  that is the whole repair. The old version waited on "Bản đồ nhóm" AND
     *  "Nhóm hay tụ ở đâu" together, as one condition, for every test that
     *  needed to stand on this screen. Those are not the same claim:
     *
     *    - "Bản đồ nhóm" is the `h1`. It is chrome, painted on the first frame
     *      after the press lands, and it is therefore GUARANTEED to arrive if
     *      the press was received at all.
     *    - "Nhóm hay tụ ở đâu" renders only where `nhietDo.kind` is
     *      `co-du-lieu` AND `khu.length > 0`. Every other outcome of that read
     *      -- 403, 404, a non-ok status, a body that will not parse, or an
     *      honest zero districts -- draws a refusal panel or nothing at all,
     *      and `BanDoNhom` does not retry. So once `/heatmap` has answered
     *      badly ONCE, that string can never appear, and a wait for it is not
     *      slow: it is unsatisfiable. It burns the full timeout and then
     *      reports "the map never opened", which is false.
     *
     *  Measured on main at 72aa478, the run that put this file on the board:
     *  case 3 loaded Khám phá in ~280ms and still spent the entire 15s here,
     *  on a machine that ran case 5 in 204ms immediately after. Not slowness
     *  -- an unsatisfiable condition, and a message naming the wrong thing.
     *
     *  So the screen-LOADS claim now belongs to exactly one case, the one
     *  whose subject it is, and the navigation cases stand on chrome only. A
     *  hiccup in `/heatmap` can now redden one case with a message that names
     *  the read, instead of three with a message that blames the button. */
    async function bamSangBanDoNhom() {
      await page.clickChu(NUT_BAN_DO);
      await doi(
        (t) => document.body.innerText.includes(t),
        `màn bản đồ nhóm mở ra sau khi bấm "${NUT_BAN_DO}"`,
        CHU_CUA_BAN_DO_NHOM[0],
      );
      await choNutYen("chu", NUT_DIEM_HEN);
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

      // This case, and only this case, owns the claim that the screen LOADS
      // rather than merely mounts -- so the heatmap read is waited for here,
      // where a failure of it reads as a failure of it. `doi` prints the
      // screen and the request log, so a refusal panel names itself instead
      // of arriving as a bare timeout.
      await doi(
        (t) => document.body.innerText.includes(t),
        `bản đồ nhóm đọc xong /heatmap và in "${CHU_CUA_BAN_DO_NHOM[1]}"`,
        CHU_CUA_BAN_DO_NHOM[1],
      );

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
      // The `h1`, not the heatmap heading, is the negative control: it is the
      // string this case has just PROVED present, so its disappearance means
      // the screen was replaced. The heatmap heading would do the job only on
      // the runs where `/heatmap` happened to answer, and read as a pass on
      // the runs where it did not -- an assertion that is vacuous exactly when
      // something is wrong.
      assert.ok(
        truoc.includes(CHU_CUA_BAN_DO_NHOM[0]),
        `trước khi bấm phải đang đứng trên "${CHU_CUA_BAN_DO_NHOM[0]}"`,
      );

      await page.clickChu(NUT_DIEM_HEN);
      await doi(
        (t) => document.body.innerText.includes(t),
        `màn Điểm hẹn hiện ra sau khi bấm "${NUT_DIEM_HEN}"`,
        CHU_CUA_DIEM_HEN,
      );

      const sau = await page.evaluate(chuTrenMan);
      assert.ok(sau.includes(CHU_CUA_DIEM_HEN), `màn Điểm hẹn phải in "${CHU_CUA_DIEM_HEN}"`);
      assert.ok(
        !sau.includes(CHU_CUA_BAN_DO_NHOM[0]),
        `Điểm hẹn thay cả màn; "${CHU_CUA_BAN_DO_NHOM[0]}" phải biến mất`,
      );
    });

    test("nút quay lại đưa về đúng tab Khám phá", async () => {
      await moKhamPha();
      await bamSangBanDoNhom();

      await choNutYen("nhan", NHAN_VE_KHAM_PHA);
      await page.clickLabel(NHAN_VE_KHAM_PHA);
      await doi(
        (t) => document.body.innerText.includes(t),
        `tab Khám phá quay lại sau khi bấm "${NHAN_VE_KHAM_PHA}"`,
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
