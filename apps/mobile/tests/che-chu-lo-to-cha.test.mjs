/* LỖ ĐANG MỞ trong `che-chu.mjs`: đường tắt `to-cha` xoá cả chữ bị chôn thật.
 *
 * ĐỌC KỸ TRƯỚC KHI SỬA FILE NÀY. Các assert dưới đây khẳng định hành vi SAI mà
 * cây hiện đang có, không phải hành vi đúng. Chúng là cọc cắm sẵn: khi ai đó vá
 * `che-chu.mjs`, ca "LỖ ĐANG MỞ" sẽ ĐỎ. Lúc đó lỗ đã được đóng — xoá ca đó và
 * đổi kỳ vọng thành `that`. Làm ngược lại (nới assert cho hết đỏ) là đóng nắp
 * lên đúng thứ file này tồn tại để giữ.
 *
 * ## Lỗ là gì
 *
 * `che-chu.mjs` dòng ~148:
 *
 *     verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "to-cha" : "that",
 *
 * Nhánh `: cha ? "to-cha"` chạy khi chữ KHÔNG đọc được (tyLe < 0.6) mà selector
 * detector nêu lại khớp một tổ tiên của chữ. `cha` tính bằng
 * `querySelectorAll(selectorTren)` rồi quét `.contains`, nên BẤT KỲ phần tử nào
 * mang selector đó là đủ — nó không cần là thứ đang thật sự được vẽ đè lên.
 *
 * Hệ quả: một dòng chữ bị chôn hoàn toàn (0/5 điểm mẫu đọc được) vẫn bị xếp
 * `to-cha`, và `laLoiThat` trả false, nên máy quét không đếm nó. Chính chuỗi
 * `ly` của kết quả in ra "chỉ 0/5 điểm mẫu đọc được" rồi vẫn cho qua.
 *
 * ## Vì sao nó với tới được app này, không phải chuyện giả định
 *
 * `querySelectorAll(".a.b")` khớp mọi phần tử có tập class là SIÊU TẬP của
 * {a,b}. react-native-web gộp các style prop giống nhau về cùng một atomic
 * class, nên một lớp phủ đục được style giống cái thẻ nó nằm trong sẽ có tập
 * class nằm gọn trong tập class của tổ tiên.
 *
 * Đo trên 9 màn đã render thật (`tools/probe-chung-lop.mjs`, main 058f07e),
 * chỉ tính phần tử có thể che thật (≥8×8px, nền đục):
 *
 *     2568/2906 cặp (kẻ che, chữ) = 88.4% sẽ bị xoá nhầm
 *     ca-nhan 93.3% · dang-ky 98.2% · len-plan 95.2%
 *
 * Hai fixture dưới đây giống hệt nhau từng byte trừ MỘT tên class trên lớp
 * phủ. Hình học che chắn y hệt, số điểm đọc được y hệt (0/5). Chỉ tên class
 * đổi — và verdict lật từ "tính là lỗi" sang "bỏ qua".
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
      server = await serve(dir);
      page = await launch(chromeBin);
      await page.viewport(390, 400);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      if (dir && existsSync(dir)) rmSync(dir, { recursive: true, force: true });
    });

    // Đối chứng. Ca này ĐÚNG hôm nay và phải còn đúng sau khi lỗ được vá — nó
    // ghim rằng fixture thật sự bị che, để ca dưới không thể được giải thích
    // bằng "chữ vốn đọc được".
    test("kẻ che mang class riêng: 'that', và tính là lỗi", async () => {
      await page.goto(`${server.url}rieng.html`, () =>
        document.body?.innerText?.includes("Ăn tối ở Đà Lạt"),
      );
      const kq = await phanLoai(page, finding("div.phu-rieng"));
      assert.equal(kq.verdict, "that", `mong 'that', nhận '${kq.verdict}' — ${kq.ly}`);
      assert.equal(laLoiThat(kq), true);
      assert.equal(kq.diemNhinThay, 0, "fixture phải chôn hẳn chữ: 0 điểm đọc được");
    });

    // LỖ ĐANG MỞ. Khi ca này ĐỎ nghĩa là `che-chu.mjs` đã được vá: xoá ca này,
    // và đổi kỳ vọng thành `verdict === "that"` / `laLoiThat === true`.
    test("LỖ ĐANG MỞ: kẻ che chia class với tổ tiên thì chữ bị chôn vẫn bị bỏ qua", async () => {
      await page.goto(`${server.url}chung.html`, () =>
        document.body?.innerText?.includes("Ăn tối ở Đà Lạt"),
      );
      const kq = await phanLoai(page, finding("div.khung"));

      // Chữ bị chôn y hệt ca trên — không một điểm mẫu nào đọc được.
      assert.equal(kq.diemNhinThay, 0, "cùng hình học che, phải vẫn là 0 điểm đọc được");
      assert.equal(kq.diemDo, 5);

      // ...vậy mà vẫn bị xếp là ảo ảnh và không được đếm. Đây là cái sai.
      assert.equal(
        kq.verdict,
        "to-cha",
        "nếu ca này đỏ vì nhận 'that' thì LỖ ĐÃ ĐƯỢC VÁ — xoá ca này, xem đầu file",
      );
      assert.equal(
        laLoiThat(kq),
        false,
        "nếu ca này đỏ thì LỖ ĐÃ ĐƯỢC VÁ — xoá ca này, xem đầu file",
      );
    });
  });
}
