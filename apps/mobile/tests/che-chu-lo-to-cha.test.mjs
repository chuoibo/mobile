/* Chữ bị chôn hoàn toàn phải là lỗi, kể cả khi kẻ che chia class với tổ tiên.
 *
 * Đây là ca hồi quy cho lỗ mà `#255` để lại và `#259` (qa-tt-0012) đo được.
 * `che-chu.mjs` từng viết vế phán quyết như sau:
 *
 *     verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "to-cha" : "that",
 *                                                              ^^^^^^^^^^^^^^^
 *
 * Nhánh được gạch chân chạy khi chữ KHÔNG đọc được (tyLe < 0.6) mà selector
 * detector in ra lại khớp một tổ tiên nào đó của chữ. `cha` tính bằng
 * `querySelectorAll(selectorTren)` rồi quét `.contains`, nên chỉ cần CÓ MỘT
 * phần tử mang selector đó là đủ — nó không cần là thứ đang thật sự vẽ đè lên.
 * Hệ quả: `laLoiThat` trả false cho một dòng chữ bị chôn 0/5 điểm mẫu, và
 * chính chuỗi `ly` in ra "chỉ 0/5 điểm mẫu đọc được" rồi vẫn cho qua.
 *
 * Với tới được app này chứ không phải chuyện giả định: `querySelectorAll(".a.b")`
 * khớp mọi phần tử có tập class là SIÊU TẬP của {a,b}, mà react-native-web gộp
 * các style prop giống nhau về cùng một atomic class. QA đo trên 9 màn đã render
 * thật (`tools/probe-chung-lop.mjs` ở #259), chỉ tính phần tử che được thật
 * (>=8x8px, nền đục): 2568/2906 cặp = 88.4% sẽ bị xoá nhầm.
 *
 * ## Vì sao bản vá là XOÁ nhánh đó, không phải siết lại phép kiểm `cha`
 *
 * Câu hỏi "kẻ che có phải tổ tiên không" đã được trả lời ở trên rồi, bằng chính
 * ngăn xếp hit-test chứ không bằng selector: vòng lấy mẫu đếm một điểm là ĐỌC
 * ĐƯỢC khi phần tử trên cùng là `el`, là con của `el`, HOẶC là tổ tiên của `el`
 * (`tren.contains(el)`). Nên một tổ tiên nằm đè lên chữ đã được tính vào
 * `nhinThay` rồi. Xuống tới vế `tyLe < 0.6` nghĩa là đa số điểm mẫu có thứ
 * KHÔNG phải tổ tiên nằm trên cùng — theo đúng định nghĩa, `to-cha` không bao
 * giờ giải thích được vế đó. Nhánh ấy không siết được, nó chỉ đúng khi bị xoá.
 *
 * ## Hai fixture
 *
 * Giống hệt nhau từng byte trừ ĐÚNG MỘT tên class trên lớp phủ. Hình học che y
 * hệt, số điểm đọc được y hệt (0/5). Trước bản vá verdict lật từ "tính là lỗi"
 * sang "bỏ qua" chỉ vì tên class; sau bản vá cả hai đều là `that`.
 *
 * Ca `.phu-rieng` là ĐỐI CHỨNG: nó đúng cả trước lẫn sau bản vá. Giữ nó để ca
 * `.khung` không thể được giải thích bằng "fixture vốn đọc được".
 *
 * Cái này KHÔNG chứng minh: rằng ngưỡng 0.6 đặt đúng chỗ, rằng detector bắn
 * đúng nơi cần bắn, hay rằng màn thật nào đang sạch.
 */
import assert from "node:assert/strict";
import test, { after, before, describe } from "node:test";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { laLoiThat, phanLoai } from "../tools/che-chu.mjs";
import { findChrome, launch, serve } from "./chrome-cdp.mjs";

/** Lớp phủ mang class RIÊNG — không phần tử nào khác có `.phu-rieng`. */
const RIENG = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>rieng</title></head><body style="margin:0;font:16px system-ui">
<div class="khung" style="position:relative;padding:40px 16px">
  <div class="tieu-de">Ăn tối ở Đà Lạt</div>
  <div class="phu-rieng" style="position:absolute;left:0;right:0;top:32px;height:40px;background:#123456"></div>
</div>
</body></html>`;

/** Cùng trang, cùng lớp phủ, cùng hình học. Lớp phủ chỉ mang thêm `khung` —
 *  đúng cái class mà ông nội của chữ đã có. */
const CHUNG = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>chung</title></head><body style="margin:0;font:16px system-ui">
<div class="khung" style="position:relative;padding:40px 16px">
  <div class="tieu-de">Ăn tối ở Đà Lạt</div>
  <div class="khung" style="position:absolute;left:0;right:0;top:32px;height:40px;background:#123456"></div>
</div>
</body></html>`;

/** Không có lớp phủ nào. Nhãn nằm trong một cái thẻ có nền của chính nó —
 *  đúng hình dạng mà detector mô tả thành "bị `div.khung` che". Chữ đọc được. */
const CHA_DOC_DUOC = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>cha doc duoc</title></head><body style="margin:0;font:16px system-ui">
<div class="khung" style="background:#f2f2f2;padding:24px 16px">
  <div class="tieu-de">Giao dịch gần đây</div>
</div>
</body></html>`;

const finding = (sel) => ({
  antipattern: "text-occlusion",
  snippet: `div.tieu-de "Ăn tối ở Đà Lạt" is 100% covered by an opaque element (${sel})`,
});

const chromeBin = findChrome();
const REQUIRED = process.env.MOBILE_REQUIRE_CHE_CHU === "1";

if (!chromeBin && !REQUIRED) {
  test("lỗ to-cha — BỎ QUA: không tìm thấy Chrome", { skip: "không tìm thấy Chrome" }, () => {});
} else {
  describe("đường tắt to-cha, đo trên trang render thật", () => {
    let page;
    let server;
    let dir;

    before(async () => {
      assert.ok(chromeBin, "MOBILE_REQUIRE_CHE_CHU=1 nhưng không tìm thấy Chrome");
      dir = mkdtempSync(join(tmpdir(), "lo-to-cha-"));
      writeFileSync(join(dir, "rieng.html"), RIENG);
      writeFileSync(join(dir, "chung.html"), CHUNG);
      writeFileSync(join(dir, "cha-doc-duoc.html"), CHA_DOC_DUOC);
      server = await serve(dir);
      page = await launch(chromeBin);
      await page.viewport(390, 400);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      if (dir && existsSync(dir)) rmSync(dir, { recursive: true, force: true });
    });

    // Đối chứng: đúng cả trước lẫn sau bản vá. Nó ghim rằng fixture thật sự bị
    // che, để ca dưới không thể được giải thích bằng "chữ vốn đọc được".
    test("kẻ che mang class riêng: 'that', và tính là lỗi", async () => {
      await page.goto(`${server.url}rieng.html`, () =>
        document.body?.innerText?.includes("Ăn tối ở Đà Lạt"),
      );
      const kq = await phanLoai(page, finding("div.phu-rieng"));
      assert.equal(kq.verdict, "that", `mong 'that', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), true);
      assert.equal(kq.diemNhinThay, 0, "fixture phải chôn hẳn chữ: 0 điểm đọc được");
    });

    // Ca hồi quy. ĐỎ trên cây trước bản vá (nhận 'to-cha', laLoiThat false).
    test("kẻ che chia class với tổ tiên: vẫn 'that', vẫn tính là lỗi", async () => {
      await page.goto(`${server.url}chung.html`, () =>
        document.body?.innerText?.includes("Ăn tối ở Đà Lạt"),
      );
      const kq = await phanLoai(page, finding("div.khung"));

      // Chữ bị chôn y hệt ca trên — không một điểm mẫu nào đọc được.
      assert.equal(kq.diemNhinThay, 0, "cùng hình học che, phải vẫn là 0 điểm đọc được");
      assert.equal(kq.diemDo, 5);

      assert.equal(
        kq.verdict,
        "that",
        `chữ bị chôn 0/5 điểm thì tên class của kẻ che không được đổi phán quyết; nhận '${kq.verdict}' — ${kq.ly}`,
      );
      assert.equal(laLoiThat(kq), true, "chữ bị chôn phải còn được đếm vào cổng");
    });

    // Vế "đọc được" không đổi: `to-cha` vẫn là câu trả lời cho một cái thẻ có
    // nền của chính nó, và vẫn không tính là lỗi. Bản vá chỉ đụng vế không đọc
    // được, và ca này là chỗ chứng minh nó không đụng quá tay.
    test("thẻ có nền phủ chính nhãn của nó: vẫn 'to-cha', vẫn KHÔNG tính là lỗi", async () => {
      await page.goto(`${server.url}cha-doc-duoc.html`, () =>
        document.body?.innerText?.includes("Giao dịch gần đây"),
      );
      const kq = await phanLoai(page, {
        antipattern: "text-occlusion",
        snippet: 'div.tieu-de "Giao dịch gần đây" is 41% covered by an opaque element (div.khung)',
      });
      assert.equal(kq.diemNhinThay, 5, "fixture này chữ phải đọc được: 5/5 điểm");
      assert.equal(kq.verdict, "to-cha", `mong 'to-cha', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), false);
    });
  });
}
