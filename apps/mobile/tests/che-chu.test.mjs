/* `che-chu.mjs` must tell a buried heading apart from one that merely scrolled away.
 *
 * The scanners are about to stop counting most `text-occlusion` warnings, and
 * that is only safe if the thing deciding which ones to drop can still spot a
 * real one. A filter that answers "artifact" to everything turns four warnings
 * green and would look exactly like this file passing.
 *
 * So the fixtures are synthetic and both directions are asserted:
 *
 *   che-that    an opaque sibling painted over a heading, fully in view
 *               -> `that`, and `laLoiThat` true
 *   cuon-khuat  a row below its scroll container's clip edge, with a pinned
 *               footer sitting at those same coordinates -- the shape that
 *               produced three false findings on `ban-be` and `dia-diem`
 *               -> `cuon-khuat`, and `laLoiThat` false
 *   to-cha      a label inside a card that has a background of its own, which
 *               is how the rule described `ca-nhan`'s "Giao dịch gần đây"
 *               -> `to-cha`, and `laLoiThat` false
 *
 * Synthetic rather than driven off the real screens on purpose: a fixture
 * cannot be quietly fixed by somebody restyling a card, so a later green here
 * keeps meaning what it means today. The real screens are covered by
 * `quet-tab-url.mjs`, which is where a regression in the app belongs.
 *
 * What this does NOT prove: that the detector's rule fires where it should, or
 * that any real screen is clean. It proves only that the adjudicator's two
 * answers are both reachable.
 */
import assert from "node:assert/strict";
import test, { after, before, describe } from "node:test";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { docSnippet, laLoiThat, phanLoai } from "../tools/che-chu.mjs";
import { findChrome, launch, serve } from "./chrome-cdp.mjs";

/* ---------------------------------------------------------------- fixtures --- */

/** An opaque box painted over the words, as a sibling. A real defect. */
const CHE_THAT = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>che that</title></head><body style="margin:0;font:16px system-ui">
<div style="position:relative;padding:40px 16px">
  <div class="tieu-de">Ăn tối ở Đà Lạt</div>
  <div class="phu" style="position:absolute;left:0;right:0;top:32px;height:40px;background:#123456"></div>
</div>
</body></html>`;

/** The `ban-be` shape: the last row sits below the clip edge of a scroll
 *  container, and a pinned footer occupies those coordinates. Nothing is on
 *  top of the words -- they are simply not scrolled to yet. */
const CUON_KHUAT = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>cuon khuat</title></head><body style="margin:0;font:16px system-ui">
<div id="ds" style="position:absolute;top:0;left:0;right:0;height:300px;overflow-y:auto;background:#fff">
  ${Array.from({ length: 14 }, (_, i) => `<div style="height:40px">Hàng ${i + 1}</div>`).join("")}
  <div style="height:40px">Phạm Hoàng Anh Thư</div>
</div>
<button class="chan" style="position:fixed;left:0;right:0;top:320px;height:48px;background:#eeeeee;border:0">Đóng</button>
</body></html>`;

/** The `ca-nhan` shape: the "occluder" is the card the label lives inside. */
const TO_CHA = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>to cha</title></head><body style="margin:0;font:16px system-ui">
<div class="the" style="background:#f2f2f2;padding:24px 16px">
  <div>Giao dịch gần đây</div>
</div>
</body></html>`;

const finding = (snippet) => ({ antipattern: "text-occlusion", snippet });

/* -------------------------------------------------------------------- gate --- */

const chromeBin = findChrome();
const REQUIRED = process.env.MOBILE_REQUIRE_CHE_CHU === "1";

test("docSnippet đọc được đúng hình dạng câu detector in ra", () => {
  const d = docSnippet(
    'div.css-146c3p1 "Bạn bè từ 22/08" is 100% covered by an opaque element (button.css-g5y9jx.r-1loqt21)',
  );
  assert.equal(d.chu, "Bạn bè từ 22/08");
  assert.equal(d.phanTram, 100);
  assert.equal(d.tren, "button.css-g5y9jx.r-1loqt21");
  // A snippet from some other rule must not be mistaken for one of these.
  assert.equal(docSnippet("~16px used 7/11 times (64%)"), null);
});

if (!chromeBin && !REQUIRED) {
  test("phân loại che chữ — BỎ QUA: không tìm thấy Chrome", { skip: "không tìm thấy Chrome" }, () => {});
} else {
  describe("phân loại che chữ, đo trên trang render thật", () => {
    let page;
    let server;
    let dir;

    before(async () => {
      assert.ok(chromeBin, "MOBILE_REQUIRE_CHE_CHU=1 nhưng không tìm thấy Chrome");
      dir = mkdtempSync(join(tmpdir(), "che-chu-"));
      writeFileSync(join(dir, "che-that.html"), CHE_THAT);
      writeFileSync(join(dir, "cuon-khuat.html"), CUON_KHUAT);
      writeFileSync(join(dir, "to-cha.html"), TO_CHA);
      server = await serve(dir);
      page = await launch(chromeBin);
      await page.viewport(390, 400);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      if (dir && existsSync(dir)) rmSync(dir, { recursive: true, force: true });
    });

    test("chữ bị hộp đục đè lên: 'that', và tính là lỗi", async () => {
      await page.goto(`${server.url}che-that.html`, () =>
        document.body?.innerText?.includes("Ăn tối ở Đà Lạt"),
      );
      const kq = await phanLoai(page, finding('div.tieu-de "Ăn tối ở Đà Lạt" is 100% covered by an opaque element (div.phu)'));
      assert.equal(kq.verdict, "that", `mong 'that', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), true);
    });

    test("chữ nằm dưới mép vùng cuộn: 'cuon-khuat', và KHÔNG tính là lỗi", async () => {
      await page.goto(`${server.url}cuon-khuat.html`, () =>
        document.body?.innerText?.includes("Hàng 1"),
      );
      const kq = await phanLoai(
        page,
        finding('div "Phạm Hoàng Anh Thư" is 100% covered by an opaque element (button.chan)'),
      );
      assert.equal(kq.verdict, "cuon-khuat", `mong 'cuon-khuat', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), false);
    });

    test("'kẻ che' là tổ tiên của chính chữ: 'to-cha', và KHÔNG tính là lỗi", async () => {
      await page.goto(`${server.url}to-cha.html`, () =>
        document.body?.innerText?.includes("Giao dịch gần đây"),
      );
      const kq = await phanLoai(
        page,
        finding('div "Giao dịch gần đây" is 41% covered by an opaque element (div.the)'),
      );
      assert.equal(kq.verdict, "to-cha", `mong 'to-cha', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), false);
    });

    test("chữ không có trên trang thì báo 'khong-thay', không im lặng cho qua", async () => {
      await page.goto(`${server.url}to-cha.html`, () =>
        document.body?.innerText?.includes("Giao dịch gần đây"),
      );
      const kq = await phanLoai(
        page,
        finding('div "Chuỗi không tồn tại ở đâu cả" is 100% covered by an opaque element (div.the)'),
      );
      assert.equal(kq.verdict, "khong-thay");
      // Fails closed: an answer the filter does not recognise keeps the
      // warning rather than clearing it.
      assert.equal(laLoiThat(kq), true);
    });

    test("verdict lạ hoắc vẫn giữ cảnh báo, không mặc định cho qua", () => {
      assert.equal(laLoiThat({ verdict: "mot-verdict-chua-tung-co" }), true);
      assert.equal(laLoiThat({}), true);
      assert.equal(laLoiThat(null), true);
    });
  });
}
