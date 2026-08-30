/* Hearts and comments on the memory wall, measured on a live render (rd-fe-33).
 *
 * Every claim in this file is about state that only exists after a press, so
 * none of it can be read out of the source. The heart chooses POST or DELETE
 * from `viewer_has_reacted`, the count that comes back is the server's, and the
 * comment count only moves when the wall re-reads itself. `renderToStaticMarkup`
 * can express none of those.
 *
 * ## The anchor is the aria-label, and that is deliberate
 *
 * Assertions here match on `[aria-label="..."]`, whose text carries BOTH the
 * count and the state: "Thả tim. Ảnh này đang có 2 tim." versus "Bỏ tim. Ảnh
 * này đang có 3 tim, trong đó có tim của bạn." So one selector proves the
 * number moved and the toggle flipped, and it is the same string a screen
 * reader announces -- there is no second, sighted-only wording that could pass
 * while the announced one rots.
 *
 * The alternative, counting elements with some class, is the trap this repo has
 * already been bitten by: react-native-web hands out shared atomic classes, so
 * any such selector is a superset of what it appears to select.
 *
 * ## What this covers that the detector scan does not
 *
 * `tools/quet-tab-url.mjs` reports zero anti-patterns on this screen. That is a
 * statement about contrast, type and geometry. It is not a statement that the
 * heart records anything: wire `onPress` to nothing and the scan still says
 * zero, because a dead Pressable is visually identical to a live one.
 *
 * ## The case that is easiest to get wrong
 *
 * `khong co bang` below strips the three social fields from the feed and
 * asserts that NO heart is drawn. That is the honest-degradation rule from
 * `TimVaBinhLuan.tsx`: the buttons exist only where pressing them can work. A
 * suite without it would pass just as happily on a build that draws hearts
 * unconditionally and 404s on every press -- which is the version of this
 * feature that ships to a demo and blames the person tapping.
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

/** The two fixture photographs, in the order the wall draws them.
 *
 *  Written out rather than derived from the fixture so that changing the
 *  fixture has to change this file too, deliberately. A list computed from the
 *  data under test agrees with whatever that data becomes. */
const TIM_CHUA_THA = "Thả tim. Ảnh này đang có 2 tim.";
const TIM_SAU_KHI_THA = "Thả tim. Ảnh này đang có 3 tim.";
const DA_THA_3 = "Bỏ tim. Ảnh này đang có 3 tim, trong đó có tim của bạn.";
const DA_THA_1 = "Bỏ tim. Ảnh này đang có 1 tim, trong đó có tim của bạn.";
const TIM_SAU_KHI_BO = "Thả tim. Ảnh này đang có 0 tim.";

const NUT_XEM_BINH_LUAN = "Xem 1 bình luận của ảnh này";
const NUT_XEM_HAI = "Xem 2 bình luận của ảnh này";
const NUT_VIET_DAU_TIEN = "Viết bình luận đầu tiên cho ảnh này";
const NUT_AN = "Ẩn bình luận của ảnh này";
const O_VIET = "Ô viết bình luận cho ảnh này";

/** The sentence the wall prints about hearts when the server has no tables. */
const NOI_CHUA_CO = "Thả tim và bình luận cũng chưa có bảng nào";
/** ...and the one it prints when it has seen a server that does. */
const NOI_DA_CO = "Hai thứ đó là việc còn lại của trụ cột 5";

const TRANG_CO = "__test-tim-co.html";
const TRANG_KHONG = "__test-tim-khong.html";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** Every aria-label on screen that names a heart. Read as a set of strings so a
 *  failure prints what the wall actually offered rather than a count. */
function nhanTim() {
  return [...document.querySelectorAll("[aria-label]")]
    .map((el) => el.getAttribute("aria-label"))
    .filter((n) => n.includes("tim"));
}

/** Does an element with exactly this aria-label exist right now? */
function coNhan(nhan) {
  return document.querySelector(`[aria-label="${nhan}"]`) !== null;
}

function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

/** The `aria-checked` the heart is actually shipping to the DOM.
 *
 *  Read as a raw attribute rather than through any helper: `ui/a11y.ts` exists
 *  because react-native-web 0.21.2 drops `accessibilityState` entirely, and the
 *  only way to know the replacement survived is to look at the rendered node. */
function ariaChecked(nhan) {
  const el = document.querySelector(`[aria-label="${nhan}"]`);
  return el === null ? "(không có nút)" : String(el.getAttribute("aria-checked"));
}

/** A fixture whose feed rows carry no social fields at all -- what a server
 *  without the two tables answers. Deleting the keys is the point: `undefined`
 *  is what `coTuongTac` keys off, and a `0` here would be a different test. */
function fixturesKhongCoBang() {
  const f = JSON.parse(JSON.stringify(taoFixtures()));
  for (const m of f.kyNiem) {
    delete m.reaction_count;
    delete m.comment_count;
    delete m.viewer_has_reacted;
  }
  return f;
}

function vietTrang(duongDan, fixtures) {
  const indexHtml = readFileSync(join(EXPORT_DIR, "index.html"), "utf8");
  const i = indexHtml.indexOf("<head>");
  assert.ok(i !== -1, "index.html không có <head> để chèn stub");
  const tiem =
    `<script>(${installTabStubs.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
  writeFileSync(duongDan, indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6));
}

if (reasons.length && !REQUIRED) {
  test(`tim và bình luận trên web — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("tường kỷ niệm: thả tim và bình luận", () => {
    let page;
    let server;
    const duongCo = join(EXPORT_DIR, TRANG_CO);
    const duongKhong = join(EXPORT_DIR, TRANG_KHONG);

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      vietTrang(duongCo, taoFixtures());
      vietTrang(duongKhong, fixturesKhongCoBang());
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(390, 844);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      for (const p of [duongCo, duongKhong]) {
        try {
          unlinkSync(p);
        } catch (err) {
          if (err.code !== "ENOENT") throw err;
        }
      }
    });

    /** Open the wall from a genuinely fresh mount.
     *
     *  The `about:blank` hop is load-bearing. `AppRoot` reads the fragment once
     *  on mount, so navigating between two urls that differ only after the `#`
     *  is a same-document navigation: React never remounts and the screen keeps
     *  whatever state the previous test left on it. Without the hop, the second
     *  test here would open a wall whose heart was already pressed and would
     *  pass or fail for reasons belonging to the first.
     *
     *  Waiting on a heart label rather than on the heading: the heading paints
     *  in the error state too, so it would wave through a wall that never got
     *  its photographs. */
    async function moTuong(trang, cho) {
      await page.goto("about:blank");
      await page.goto(
        `${server.url}${trang}#vao=ky-niem&nguoi=${NGUOI}`,
        (n) => document.querySelector(`[aria-label="${n}"]`) !== null ||
          document.body.innerText.includes(n),
        cho,
      );
    }

    test("máy chủ có bảng: hai ảnh, một tim rỗng và một tim đã thả", async () => {
      await moTuong(TRANG_CO, TIM_CHUA_THA);
      const nhan = await page.evaluate(nhanTim);
      console.log(`  nhãn tim trên màn: ${nhan.join(" | ")}`);
      assert.deepEqual(
        nhan.sort(),
        [TIM_CHUA_THA, DA_THA_1].sort(),
        "mỗi ảnh đúng một nút tim, và hai ảnh phải ở hai trạng thái khác nhau",
      );

      // The state has to reach the DOM, not just the props. This is the exact
      // hole `ui/a11y.ts` was written for.
      const chuaTha = await page.evaluate(ariaChecked, TIM_CHUA_THA);
      const daTha = await page.evaluate(ariaChecked, DA_THA_1);
      console.log(`  aria-checked: chưa thả=${chuaTha}, đã thả=${daTha}`);
      assert.equal(chuaTha, "false", "tim chưa thả phải ra DOM với aria-checked=false");
      assert.equal(daTha, "true", "tim đã thả phải ra DOM với aria-checked=true");
    });

    test("thả tim: số đếm lên đúng một, và nút đổi sang trạng thái đã thả", async () => {
      await moTuong(TRANG_CO, TIM_CHUA_THA);
      await page.clickLabel(TIM_CHUA_THA);
      await page.waitFor(
        (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
        { label: "tường đọc lại xong sau khi thả tim" },
        DA_THA_3,
      );

      const nhan = await page.evaluate(nhanTim);
      console.log(`  sau khi thả: ${nhan.join(" | ")}`);
      assert.ok(
        nhan.includes(DA_THA_3),
        `sau khi thả phải thành "${DA_THA_3}" -- số đếm là số máy chủ trả về`,
      );
      assert.ok(
        !nhan.includes(TIM_CHUA_THA),
        "nút cũ không được còn: nó vẫn nói 2 tim và vẫn gửi POST",
      );
      assert.equal(
        await page.evaluate(ariaChecked, DA_THA_3),
        "true",
        "aria-checked phải theo trạng thái mới",
      );
    });

    /* The DELETE half, and the only test in the suite that touches a 204.
     *
     * `call()` in `api.ts` used to run `response.json()` on every success. An
     * empty 204 body makes that throw a raw SyntaxError -- not an `ApiError` --
     * so it escaped every refusal table in the file and would have painted the
     * browser's own English parser message under a photograph, for a call the
     * server had just carried out successfully. Nothing else here answers 204,
     * so removing that branch fails this test and only this test. */
    test("bỏ tim: 204 không thân vẫn được đọc là thành công, số đếm về 0", async () => {
      await moTuong(TRANG_CO, DA_THA_1);
      await page.clickLabel(DA_THA_1);
      await page.waitFor(
        (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
        { label: "tường đọc lại xong sau khi bỏ tim" },
        TIM_SAU_KHI_BO,
      );

      const nhan = await page.evaluate(nhanTim);
      console.log(`  sau khi bỏ: ${nhan.join(" | ")}`);
      assert.ok(nhan.includes(TIM_SAU_KHI_BO), "bỏ tim xong ảnh đó phải còn 0 tim");
      assert.ok(
        nhan.includes(TIM_CHUA_THA),
        "ảnh kia không được động vào: 204 chỉ gỡ tim của chính người bấm",
      );

      // The failure this is really guarding: a thrown SyntaxError lands in the
      // catch and paints a sentence under the photo. There must be none.
      const chu = await page.evaluate(chuTrenMan);
      assert.ok(
        !chu.includes("Chưa gửi được tim"),
        "một 204 đọc thành công thì không được hiện câu lỗi nào",
      );
      assert.ok(
        !/JSON|Unexpected end of|SyntaxError/i.test(chu),
        `không được để chữ của máy lọt ra màn: ${chu.slice(0, 200)}`,
      );
    });

    test("bình luận: đọc được câu đã có, gửi thêm một câu thì số đếm lên theo", async () => {
      await moTuong(TRANG_CO, NUT_XEM_BINH_LUAN);
      await page.clickLabel(NUT_XEM_BINH_LUAN);
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "bình luận cũ hiện ra" },
        "Quang Huy",
      );

      let chu = await page.evaluate(chuTrenMan);
      assert.ok(
        chu.includes("Chuyến này vui xỉu luôn"),
        "câu bình luận có sẵn phải hiện đủ, kèm tên người viết",
      );

      await page.typeInto(O_VIET, "Đi nữa đi mọi người");
      await page.clickLabel("Gửi bình luận");
      await page.waitFor(
        (t) => document.body.innerText.includes(t),
        { label: "câu vừa gửi hiện ra" },
        "Đi nữa đi mọi người",
      );

      // The count lives on the feed, not on the open list. If the wall does not
      // re-read after a successful post, the list grows and the count does
      // not -- which on screen reads as a comment that failed to save.
      //
      // Read with the panel CLOSED, because that is the only state in which the
      // button spells the number out: open, it says "Ẩn bình luận". Closing it
      // is also the honest walk -- a person posts, collapses, and sees whether
      // what they wrote is counted.
      await page.clickLabel(NUT_AN);
      await page.waitFor(
        (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
        { label: "số đếm bình luận lên theo sau khi thu gọn" },
        NUT_XEM_HAI,
      );
      chu = await page.evaluate(chuTrenMan);
      console.log(`  nút bình luận sau khi gửi: ${NUT_XEM_HAI}`);
      assert.ok(
        !chu.includes("Chưa gửi được bình luận"),
        "gửi thành công thì không được hiện câu lỗi",
      );
    });

    /* Honest degradation. This is the test that separates "the feature works"
     * from "the buttons are drawn". */
    test("máy chủ KHÔNG có bảng: không vẽ nút tim nào, và nói thẳng là chưa dựng", async () => {
      await moTuong(TRANG_KHONG, "Sáng Đà Lạt, sương chưa tan");
      const nhan = await page.evaluate(nhanTim);
      console.log(`  nhãn tim khi máy chủ không có bảng: ${nhan.join(" | ") || "(không có)"}`);
      assert.deepEqual(
        nhan,
        [],
        "feed không có ba trường xã hội thì không được vẽ nút tim nào",
      );
      assert.equal(
        await page.evaluate(coNhan, NUT_VIET_DAU_TIEN),
        false,
        "cũng không được vẽ nút bình luận",
      );

      const chu = await page.evaluate(chuTrenMan);
      assert.ok(
        chu.includes(NOI_CHUA_CO),
        `phải nói thẳng là chưa có bảng nào, thấy: ${chu.slice(0, 300)}`,
      );
      assert.ok(
        !chu.includes(NOI_DA_CO),
        "không được nói thả tim đã dựng xong khi máy chủ không giữ được nó",
      );
    });

    /* The other side of the same sentence: once the wall HAS seen a server that
     * holds hearts, it must stop listing them as unbuilt. A screen that draws a
     * working heart and a line saying hearts do not exist is worse than either. */
    test("máy chủ có bảng: câu 'chưa dựng' bỏ thả tim ra khỏi danh sách", async () => {
      await moTuong(TRANG_CO, TIM_CHUA_THA);
      const chu = await page.evaluate(chuTrenMan);
      assert.ok(
        chu.includes(NOI_DA_CO),
        `phải rút xuống còn hai thứ chưa dựng, thấy: ${chu.slice(0, 300)}`,
      );
      assert.ok(
        !chu.includes(NOI_CHUA_CO),
        "không được vừa vẽ tim bấm được vừa nói thả tim chưa có bảng nào",
      );
    });
  });
}
