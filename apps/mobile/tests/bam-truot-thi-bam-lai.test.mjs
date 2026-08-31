/* Một cú bấm bị rơi thì máy lái bấm lại; một cái nút chết thì vẫn phải đỏ.
 *
 * ## Lỗi có thật, đo được, không phải giả thuyết
 *
 * `duong-vao-mon-cua-toi.test.mjs` đỏ khoảng 1/10 lượt trên máy này — 2 lần
 * trong 20 lượt `node --test` đo liên tiếp cùng một SHA. Lượt đỏ in ra:
 *
 *     [nhịp] "mở Món của tôi": 17 bước, chờ lâu nhất 505ms
 *     het gio cho "Danh sách gửi lên thay hết món bạn nhận trước đó"
 *         sau 20038ms (ngan sach 20000ms)
 *     ms mỗi bước: [505,41,6,145,0,11,2,5,44,8,4,131,57,2,29,89,1]
 *
 * Bước cuối cùng chạy xong là `{"bamChu":"Món của tôi"}` và nó tốn **1ms**.
 * Mọi bước đều dưới 505ms, rồi màn đích không bao giờ tới. Đó không phải máy
 * chậm — nới ngân sách lên 60s cũng không cứu, vì cái màn ấy sẽ không tới nữa.
 * Đó là **một cú bấm bị rơi**: `el.click()` bắn đi rồi báo thành công ngay,
 * và máy lái không có cách nào phân biệt "đã bấm trúng" với "bấm xong không ai
 * nghe".
 *
 * ## Vì sao ca này đo được cái mà ca kia không đo được
 *
 * Lỗi thật chỉ hiện ~1/10 lượt, nên "chạy 8 lượt xanh" không chứng minh gì:
 * xác suất 8 lượt xanh liên tiếp khi chưa sửa gì đã là 43%. Ca này **ép** cú
 * bấm rơi, nên nó đỏ 100% ở bản chưa sửa và xanh 100% ở bản đã sửa.
 *
 * Nó không dựng app, không cần bundle expo, không cần server API. Nó chỉ dựng
 * đúng `laiTrongTrang` — thứ đang được sửa — trên ba trang HTML tự viết, nên
 * cái gì đỏ ở đây là máy lái đỏ chứ không phải màn hình đỏ.
 *
 * ## Ba hàng, và hàng thứ hai mới là hàng khó
 *
 *   1. NUỐT MỘT CÚ — nút bỏ qua cú bấm đầu, ăn cú thứ hai. Bản chưa sửa: đỏ.
 *      Bản đã sửa: xanh, và `bam_lai` ghi đúng 1 lần.
 *   2. NÚT CHẾT — nút không bao giờ làm gì. Phải **vẫn đỏ**. Đây là đối chứng
 *      âm: nếu bấm lại làm ca này xanh thì bản sửa đã biến một lỗi thật thành
 *      một dấu xanh, và như thế còn tệ hơn cái flake ban đầu.
 *   3. NÚT TỐT — ăn ngay cú đầu. `bam_lai` phải **rỗng**. Đây là đối chứng
 *      chống bấm thừa: một máy lái bấm lại vô tội vạ sẽ gửi "Lưu" hai lần.
 *
 * Chạy:
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/bam-truot-thi-bam-lai.test.mjs
 */
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { laiTrongTrang } from "../tools/quet-man-sau-tap.mjs";

const NHAN = "Đi tiếp";
const DICH = "Đã tới màn sau";

/** Trang chỉ có một nút, và một quy tắc về việc nó nghe cú bấm thứ mấy.
 *
 *  `boQua` = số cú bấm đầu bị nuốt. `Infinity` là nút chết hẳn. Nút thật, thẻ
 *  `<button>` thật, `addEventListener("click")` thật — nên cái được đo là máy
 *  lái, không phải cách react-native-web dựng sự kiện. */
function trangNut(boQua, kichBan) {
  return (
    "<!doctype html><html><head><meta charset=utf-8>" +
    `<script>(${laiTrongTrang.toString()})(${JSON.stringify(kichBan)},null);<\/script>` +
    "</head><body>" +
    `<button id=n>${NHAN}</button><div id=d></div>` +
    "<script>var dem=0;var bo=" +
    (boQua === Infinity ? "Infinity" : String(boQua)) +
    ";document.getElementById('n').addEventListener('click',function(){" +
    "dem++;if(dem>bo){document.getElementById('d').textContent=" +
    JSON.stringify(DICH) +
    ";}});<\/script>" +
    "</body></html>"
  );
}

const chromeBin = findChrome();
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

if (!chromeBin && !REQUIRED) {
  test("bấm trượt thì bấm lại — BỎ QUA: no Chrome found", { skip: "no Chrome" }, () => {});
} else {
  describe("một cú bấm bị rơi, trên trang render thật", () => {
    let page;
    let server;
    let thuMuc;

    before(async () => {
      assert.ok(chromeBin, "MOBILE_REQUIRE_WEB_A11Y=1 nhưng không tìm thấy Chrome");
      thuMuc = mkdtempSync(join(tmpdir(), "bam-truot-"));
      server = await serve(thuMuc);
      page = await launch(chromeBin);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      if (thuMuc) rmSync(thuMuc, { recursive: true, force: true });
    });

    /** Dựng trang, chạy máy lái trên đó, trả về nguyên `window.__lai`. */
    async function chay(ten, boQua, ms) {
      const kichBan = [{ bamChu: NHAN }, { cho: DICH, ms }];
      writeFileSync(join(thuMuc, ten), trangNut(boQua, kichBan));
      await page.viewport(390, 844);
      await page.goto(server.url + ten);
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 120000,
        label: `máy lái trên ${ten}`,
      });
      return page.evaluate(() => ({
        xong: window.__lai.xong,
        loi: window.__lai.loi,
        bam_lai: window.__lai.bam_lai,
      }));
    }

    test("NUỐT MỘT CÚ: bấm rơi thì máy lái bấm lại và đi tiếp được", async () => {
      const lai = await chay("nuot-mot.html", 1, 20000);

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(lai.xong, true, "máy lái chưa xong");
      // Đúng MỘT lần bấm lại. Nhiều hơn nghĩa là nó bấm cả sau khi đã tới nơi.
      assert.equal(
        lai.bam_lai.length,
        1,
        `phải bấm lại đúng 1 lần, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      assert.equal(lai.bam_lai[0].cho, DICH);
      console.log(`  [nuốt một] cứu được, bấm lại ${lai.bam_lai.length} lần`);
    });

    test("NÚT CHẾT: bấm lại KHÔNG biến một lỗi thật thành dấu xanh", async () => {
      const lai = await chay("nut-chet.html", Infinity, 8000);

      assert.equal(lai.xong, false, "nút chết mà máy lái báo xong — bản sửa đang che lỗi");
      assert.match(
        String(lai.loi),
        /het gio cho/,
        `phải chết vì hết giờ chờ, thực tế: ${lai.loi}`,
      );
      // Đã thử lại đủ số lần rồi mới bỏ cuộc, chứ không phải chưa thử đã đỏ.
      assert.equal(
        lai.bam_lai.length,
        2,
        `phải thử lại 2 lần rồi mới bỏ, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      console.log(`  [nút chết] vẫn đỏ đúng như phải thế, đã thử ${lai.bam_lai.length} lần`);
    });

    test("NÚT TỐT: ăn ngay cú đầu thì KHÔNG bấm lần nào nữa", async () => {
      const lai = await chay("nut-tot.html", 0, 20000);

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(lai.xong, true, "máy lái chưa xong");
      // Đây là ca chặn "Lưu" bị gửi hai lần: đường hạnh phúc không bấm lại.
      assert.deepEqual(
        lai.bam_lai,
        [],
        `đường hạnh phúc không được bấm lại, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      console.log("  [nút tốt] không bấm lại lần nào");
    });
  });
}
