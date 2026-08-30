/* Hai màn bill có thật sự tới được từ vỏ 5 tab hay không.
 *
 * Lý do file này tồn tại. Màn chụp bill và màn kết quả nhận diện được dựng khi
 * `App.tsx` còn là toàn bộ ứng dụng: nó tự giữ một `Step` và tự vẽ từng màn.
 * Vỏ 5 tab vào `main` sau, và cũng viết lại `App.tsx` — lần này gốc app chỉ còn
 * dựng `AppRoot`, còn luồng khoản chi tụt xuống làm một render prop mà vỏ gọi
 * từ menu [+]. Đưa hai nhánh về chung một nền mà lấy nguyên `App.tsx` của
 * `main` thì hai file màn bill vẫn nằm trong repo, vẫn biên dịch, vẫn qua
 * `tsc`, và không ai gọi tới. Chúng thành mã chết.
 *
 * Kiểu hỏng đó không có triệu chứng: cây xanh, typecheck xanh, `expo export`
 * xanh, PR nhìn như đã gộp xong. Thứ duy nhất nói ra được là bản dựng — Metro
 * chỉ đóng gói module nào đi tới được từ điểm vào, nên một màn không ai import
 * thì KHÔNG có mặt trong chunk nào cả. Nên phép đo ở đây đọc artifact, giống
 * `base-url.test.mjs`, chứ không đọc mã nguồn: mã nguồn có `ChupBill.tsx` cả
 * trong bản hỏng lẫn bản đúng.
 *
 * `npm test` chạy `build:check` trước, nên phép đo này không tốn thêm lần dựng.
 *
 * Cái nó KHÔNG chứng minh, nói ra để không ai đọc quá dấu xanh: có mặt trong
 * bundle nghĩa là màn đi tới được từ đồ thị module, không phải là ngón tay
 * người dùng bấm tới được nó. Đường bấm thật (menu [+] → "Tạo khoản chi") là
 * việc của ảnh chụp màn hình và của người gác PR.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/**
 * Trả chuỗi trong mã đã rút gọn về đúng ký tự của nó.
 *
 * Bẫy, và nó suýt làm cả file này vô nghĩa: Metro rút gọn xong thì thoát mọi
 * ký tự ngoài ASCII thành `\xe1`, `ả`. Trong chunk, "Khám phá" nằm dưới
 * dạng `Kh\xe1m ph\xe1`, nên `code.includes("Khám phá")` KHÔNG BAO GIỜ khớp —
 * kể cả khi màn đó có mặt đầy đủ. Bản đầu của file này đo như thế và cho ra
 * 4/4 đỏ ở trạng thái hỏng, trông y như một phép đo tốt; nhưng nó cũng sẽ đỏ
 * 4/4 sau khi sửa xong, tức là nó không phân biệt được gì cả.
 *
 * Dấu hiệu bắt được: phép đo đối chứng "vỏ 5 tab vẫn còn" cũng đỏ, trong khi
 * vỏ chắc chắn đang có trong bản dựng. Một phép đo mà cả ca đúng lẫn ca sai
 * đều đỏ thì nó đang đo chính nó.
 */
function decode(code) {
  return code
    .replace(/\\u\{([0-9a-fA-F]+)\}/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\x([0-9a-fA-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
}

/** Every JS chunk the current build emitted, joined and unescaped. */
function builtCode() {
  // bug-010019. These assertions read a prebuilt bundle, so an export older
  // than the tree lets a screen that was deleted still "đi được vào bản dựng",
  // and a screen just added look absent. Neither answer is about this tree.
  const banCu = lyDoBanDungCu(join(ROOT, ".expo-build-check"), ROOT);
  assert.equal(banCu, null, banCu ?? "");

  const dir = join(ROOT, ".expo-build-check/_expo/static/js/web");
  let names;
  try {
    names = readdirSync(dir).filter((name) => name.endsWith(".js"));
  } catch {
    assert.fail(
      "khong tim thay ban dung web. Chay `npm run build:check` truoc, " +
        "hoac chay `npm test` (no tu dung truoc khi test).",
    );
  }
  assert.ok(
    names.length > 0,
    "thu muc ban dung rong: khong co chunk .js nao de doc — moi phep do duoi " +
      "day se dong y voi bat cu dieu gi test muon nghe.",
  );
  return decode(names.map((name) => readFileSync(join(dir, name), "utf8")).join("\n"));
}

test("phép đo tự kiểm: chuỗi tiếng Việt đọc lại được từ chunk đã rút gọn", () => {
  // Cổng của chính công cụ đo. Nếu Metro đổi cách thoát ký tự, mọi phép đo
  // dưới đây sẽ đỏ vì lý do sai, và ca này nói ra ngay lý do đó thay vì để
  // người đọc kết luận màn hình bị rơi mất.
  assert.equal(decode("Kh\\xe1m ph\\xe1"), "Khám phá");
  assert.ok(
    builtCode().includes("Máy chủ:"),
    "khong doc lai duoc chuoi tieng Viet nao tu ban dung — cach thoat ky tu " +
      "cua Metro da doi, `decode()` trong file nay phai duoc sua theo truoc " +
      "khi tin bat cu phep do nao ben duoi.",
  );
});

/* Câu chữ dùng làm dấu vết. Chọn dòng đặc thù của từng màn, không chọn từ
   chung như "bill" — "bill" có trong gợi ý của menu [+] ở vỏ, nên nó sẽ đúng
   ngay cả khi màn chụp bill đã rơi ra khỏi bản dựng. */
const DAU_VET = {
  "màn chụp bill": "Đưa bill vào khung hình",
  "màn kết quả nhận diện": "Kết quả nhận diện",
  // "Chỉ nhập chữ số" thì KHÔNG dùng được, dù nó nằm trong màn kết quả:
  // `NhapKhoanChi.tsx` có đúng câu đó, và màn đó luôn có trong bản dựng. Lấy
  // nó làm dấu vết thì phép đo xanh ngay cả lúc màn kết quả đã rơi mất —
  // đo đúng một lần rồi mới thấy. Câu về số lượng chỉ màn kết quả mới có.
  "sửa tay từng dòng": "Số lượng phải lớn hơn 0",
  "vỏ 5 tab": "Khám phá",
};

test("màn chụp bill đi được vào bản dựng — tức là gốc app có gọi tới nó", () => {
  const code = builtCode();
  assert.ok(
    code.includes(DAU_VET["màn chụp bill"]),
    'khong chunk nao chua "Dua bill vao khung hinh". Metro chi dong goi module ' +
      "di toi duoc tu diem vao, nen man ChupBill dang khong ai import — " +
      "nhieu kha nang App.tsx da bi lay nguyen ban cua main luc gop nhanh.",
  );
});

test("màn kết quả nhận diện đi được vào bản dựng", () => {
  const code = builtCode();
  assert.ok(
    code.includes(DAU_VET["màn kết quả nhận diện"]),
    'khong chunk nao chua "Ket qua nhan dien" — man KetQuaNhanDien dang la ma chet.',
  );
});

test("phần sửa tay từng dòng cũng đi vào bản dựng, không chỉ cái tiêu đề", () => {
  // Ràng buộc thiết kế do lead chốt: `needs_review=false` nghĩa là không tín
  // hiệu nào nổ, không phải số này đúng — nên mọi món phải sửa được. Kiểm câu
  // báo lỗi của ô nhập, vì nó chỉ tồn tại khi các ô nhập tồn tại. Một màn chỉ
  // còn tiêu đề mà mất phần sửa vẫn qua được phép đo trên.
  const code = builtCode();
  assert.ok(
    code.includes(DAU_VET["sửa tay từng dòng"]),
    "ban dung co tieu de man ket qua nhung khong co cau bao loi cua o nhap — " +
      "phan sua tay tung dong khong con di toi duoc.",
  );
});

test("và vỏ 5 tab vẫn còn — không ai gỡ vỏ đi để hai màn bill lên được gốc", () => {
  // Phép đo đối chứng. Ba phép trên xanh trở lại được bằng cách trả `App.tsx`
  // về bản của nhánh bill, tức là ném vỏ 5 tab của `main` đi. Phép này làm
  // chuyện đó đỏ, nên "xanh" chỉ có một nghĩa: cả hai nửa cùng có mặt.
  const code = builtCode();
  assert.ok(
    code.includes(DAU_VET["vỏ 5 tab"]),
    'khong chunk nao chua nhan tab "Kham pha" — vo 5 tab da roi ra khoi ban dung.',
  );
});
