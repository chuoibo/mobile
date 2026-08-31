/* Bạn bè và lời mời: cửa vào có sống trên NATIVE không, hay chỉ sống trong Chrome.
 *
 * ## Vì sao file này tồn tại
 *
 * `navigation/lien-ket.ts` nói thẳng ở đầu file: "Web only by nature --
 * `location` does not exist on a phone". Nó là thứ đọc `#vao=`, `#ban=` và
 * `#moi=`. Sản phẩm ship lên Android và iOS.
 *
 * Nên mọi màn mà cửa vào DUY NHẤT là một fragment thì trên nền tảng sản phẩm
 * thật sự ship, nó không có cửa nào cả. Đo trong Chrome thì nó xanh, vì trong
 * Chrome `location` có thật. Đó đúng là loại số đẹp mà không ai kiểm được.
 *
 * Hai màn rơi đúng vào đó trước thay đổi này:
 *   - `NhanLoiMoi` (F14, đầu NHẬN): chỉ mở được bằng `#moi=<token>`.
 *   - đầu ĐỌC của F05: chỉ `lien-ket.ts` đọc mã bạn, qua `#ban=`.
 *
 * ## File này chứng minh gì
 *
 * Render bằng `renderToStaticMarkup` dưới node trần. Node trần KHÔNG có
 * `globalThis.location` — đó chính là điều kiện của native, chứ không phải một
 * sự mô phỏng. Một cửa vào tìm thấy ở đây là cửa vào không phụ thuộc fragment.
 *
 * ## File này KHÔNG chứng minh gì
 *
 * Không chứng minh màn ĐẸP, không chứng minh tương phản, không chứng minh cỡ
 * chạm: `renderToStaticMarkup` không sinh CSS của react-native-web, nên mọi
 * câu hỏi về style ở đây là mù. Nó cũng không chạy `useEffect`, nên đây là
 * trạng thái ĐẦU của mỗi màn, không phải trạng thái sau khi gọi máy chủ.
 * Và nó không chứng minh có người bấm được thật trên máy Android — cái đó cần
 * emulator, và lượt này emulator không dùng được (ghi trong PR).
 */
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaNhan } from "../dist-test/screens/ca-nhan/CaNhan.js";
import { KetBan } from "../dist-test/screens/ca-nhan/KetBan.js";
import { LenPlan } from "../dist-test/screens/len-plan/LenPlan.js";

const { docMaLoiMoi } = await import("../dist-test/screens/len-plan/moi-vao-chuyen.js");

/** Minh, ra từ `navigation/nhom-demo.ts`. */
const MINH = { personId: "46b55e67-932b-5415-a5ee-08fb2641a4ff", ten: "Minh" };

function ve(el) {
  return renderToStaticMarkup(el);
}

/* ------------------------------------------------------------------ nền đo */

test("node trần không có location — đây là điều kiện native, không phải giả lập", () => {
  assert.equal(
    globalThis.location,
    undefined,
    "Có `location` thì mọi khẳng định dưới đây nói về Chrome chứ không nói về máy điện thoại.",
  );
});

/* ------------------------------------------------- ĐỐI CHỨNG DƯƠNG (bắt buộc)
 *
 * Luật của đợt này: một tính năng mà mình BIẾT là tới được phải được chính
 * thước đo này xếp đúng. Nếu nút "Mở màn kết bạn" trên Cá nhân — cửa vào F03/F04
 * đã có từ trước thay đổi này, không do tôi thêm — mà thước đo không thấy, thì
 * thước hỏng và mọi con số còn lại vô nghĩa.
 */

test("đối chứng dương: cửa vào F03/F04 có sẵn trên Cá nhân được thước đo này thấy", () => {
  const html = ve(
    React.createElement(CaNhan, {
      nguoi: MINH,
      onKetBan: () => {},
      doc: async () => {
        throw new Error("không được gọi khi render tĩnh");
      },
    }),
  );
  assert.match(html, /Mở màn kết bạn/);
});

/* ------------------------------------------------------------ ĐỐI CHỨNG ÂM
 *
 * Thước phải biết nói KHÔNG. Một `assert.match` trên chuỗi rỗng cũng xanh, nên
 * ở đây bắt nó phủ nhận đúng thứ chưa mở.
 */

test("đối chứng âm: chưa dán mã thì màn nhận lời mời CHƯA mở", () => {
  const html = ve(React.createElement(LenPlan, { nguoi: null, nhomPhien: null }));
  // Câu chỉ có trên chính màn NhanLoiMoi, không có trên thẻ mời dán mã.
  assert.doesNotMatch(html, /Nhận lời mời/);
  assert.doesNotMatch(html, /KHÔNG-CÓ-CHUỖI-NÀY-TRÊN-MÀN/);
});

/* ------------------------------------------------------- F05: đầu ĐỌC mã bạn */

test("F05: màn Kết bạn có ô đọc mã, không cần fragment", () => {
  const html = ve(
    React.createElement(KetBan, {
      nguoi: MINH,
      onDong: () => {},
      docMoi: async () => [],
      docBan: async () => [],
    }),
  );
  assert.match(html, /Thêm bằng mã kết bạn/);
  assert.match(html, /Đọc mã/);
});

/* ------------------------------------------------- F14: đầu NHẬN lời mời đi */

test("F14: thẻ nhận lời mời có mặt NGAY CẢ khi chưa có người và chưa có nhóm", () => {
  // Đây là trạng thái của đúng người mà tính năng này phục vụ: chưa vào nhóm
  // nào. Nếu thẻ nấp sau `nhom.kind === "xong"` thì nó vô hình với họ.
  const html = ve(React.createElement(LenPlan, { nguoi: null, nhomPhien: null }));
  assert.match(html, /Có người mời bạn đi\?/);
  assert.match(html, /Mã lời mời/);
});

test("đối chứng dương của cùng màn: lối tạo chuyến có sẵn vẫn được thấy", () => {
  const html = ve(React.createElement(LenPlan, { nguoi: MINH, nhomPhien: null }));
  assert.match(html, /Có người mời bạn đi\?/);
});

/* --------------------------------------------------- docMaLoiMoi: đọc và từ chối */

test("docMaLoiMoi đọc được cả ba dạng người ta thật sự dán", () => {
  const ma = "abcd1234EFGH_-xyz";
  assert.equal(docMaLoiMoi(ma), ma, "mã trần, đọc miệng qua bàn");
  assert.equal(docMaLoiMoi(`/outing-invites/${ma}`), ma, "đúng invite_path máy chủ gửi");
  assert.equal(docMaLoiMoi(`https://ru-di.app/outing-invites/${ma}`), ma, "link đầy đủ");
  assert.equal(docMaLoiMoi(`https://ru-di.app/outing-invites/${ma}/`), ma, "có gạch đuôi");
  assert.equal(docMaLoiMoi(`  ${ma}  `), ma, "dán kèm khoảng trắng");
});

test("docMaLoiMoi bỏ tham số theo dõi mà app chat gắn thêm", () => {
  const ma = "abcd1234EFGH";
  assert.equal(docMaLoiMoi(`https://ru-di.app/outing-invites/${ma}?fbclid=zz`), ma);
  assert.equal(docMaLoiMoi(`/outing-invites/${ma}#xem`), ma);
});

test("docMaLoiMoi từ chối thứ có thể lái request đi chỗ khác", () => {
  // Token bị nhét thẳng vào URL ở `api.ts`. Đây là hàng rào duy nhất.
  for (const xau of [
    "",
    "   ",
    "..",
    "../../people/xoa",
    "/outing-invites/../../admin",
    "abc def",
    "abc/def ghi",
    "short",
    "outing-invites",
    "accept",
    "a".repeat(200),
  ]) {
    assert.equal(docMaLoiMoi(xau), null, `phải từ chối: ${JSON.stringify(xau)}`);
  }
});

test("docMaLoiMoi không bao giờ trả về chuỗi còn gạch chéo", () => {
  for (const thu of [
    "/outing-invites/abcd1234EFGH",
    "https://x.test/a/b/c/abcd1234EFGH",
    "abcd1234EFGH",
  ]) {
    const ra = docMaLoiMoi(thu);
    if (ra !== null) {
      assert.ok(!ra.includes("/"), `còn gạch chéo: ${ra}`);
      assert.ok(!ra.includes(".."), `còn hai chấm: ${ra}`);
    }
  }
});
