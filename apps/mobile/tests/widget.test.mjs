/* F38 widget: dòng "ai · lúc nào", và lời từ chối — phần đọc được không cần render.
 *
 * Ca đáng giá nhất ở đây là ca ĐỒNG HỒ. `batDauTu` nhận `now` làm tham số chứ
 * không gọi `Date.now()` bên trong, và mọi ca dưới đây đứng ở HAI PHÍA của cùng
 * một mốc — 59 giây và 61 giây, 59 phút và 61 phút, 23 giờ và 25 giờ. Một bộ ca
 * chỉ đứng ở giữa mỗi cửa sổ sẽ vẫn XANH sau khi ai đó đổi `< 60` thành `<= 60`
 * hoặc dời mốc ngày sang mốc tuần: repo này đã có một lần đồng hồ giả đứng yên
 * làm mọi đột biến dời mốc trở nên tàng hình, và đó chính là hình dạng này.
 *
 * Cái file này KHÔNG chứng minh: rằng màn Widget render ra tấm ảnh. Chữ vẽ
 * giống hệt nhau trên một khung có ảnh và một khung đang vẽ hình thay thế, nên
 * bằng chứng cho tấm ảnh nằm ở cột `anh` của `quet-tab-url.mjs`, không nằm ở đây.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";

import {
  batDauTu,
  dongTacGia,
  loiWidget,
  moTaAnh,
  ngayVietNam,
} from "../dist-test/screens/widget/cau-chu.js";

/** 2026-08-30T20:00:00+07:00, viết ra một lần để mọi ca đếm ngược từ đây. */
const BAY_GIO = Date.parse("2026-08-30T20:00:00+07:00");
const GIAY = 1000;
const PHUT = 60 * GIAY;
const GIO = 60 * PHUT;
const NGAY = 24 * GIO;

/** Mốc `t` mili giây trước `BAY_GIO`, viết thành chuỗi ISO như máy chủ gửi. */
function truoc(ms) {
  return new Date(BAY_GIO - ms).toISOString();
}

/* --------------------------------------------------------- mốc thời gian --- */

test("dưới một phút là 'vừa xong'", () => {
  assert.equal(batDauTu(truoc(0), BAY_GIO), "vừa xong");
  assert.equal(batDauTu(truoc(59 * GIAY), BAY_GIO), "vừa xong");
});

test("đúng 60 giây đã sang phút — hai phía của mốc phút", () => {
  assert.equal(batDauTu(truoc(59 * GIAY), BAY_GIO), "vừa xong");
  assert.equal(batDauTu(truoc(60 * GIAY), BAY_GIO), "1 phút trước");
  assert.equal(batDauTu(truoc(61 * GIAY), BAY_GIO), "1 phút trước");
});

test("hai phía của mốc giờ", () => {
  assert.equal(batDauTu(truoc(59 * PHUT), BAY_GIO), "59 phút trước");
  assert.equal(batDauTu(truoc(60 * PHUT), BAY_GIO), "1 giờ trước");
});

test("hai phía của mốc ngày, và 'hôm qua' chứ không phải '1 ngày trước'", () => {
  assert.equal(batDauTu(truoc(23 * GIO), BAY_GIO), "23 giờ trước");
  assert.equal(batDauTu(truoc(24 * GIO), BAY_GIO), "hôm qua");
  assert.equal(batDauTu(truoc(47 * GIO), BAY_GIO), "hôm qua");
  assert.equal(batDauTu(truoc(48 * GIO), BAY_GIO), "2 ngày trước");
});

test("hai phía của mốc tuần: quá 7 ngày thì in NGÀY, không in số ngày", () => {
  assert.equal(batDauTu(truoc(6 * NGAY), BAY_GIO), "6 ngày trước");
  // 7 ngày trước 30/08 là 23/08.
  assert.equal(batDauTu(truoc(7 * NGAY), BAY_GIO), "23/08/2026");
});

test("mốc ở tương lai đọc là 'vừa xong', không phải số âm", () => {
  // Lệch đồng hồ giữa máy và máy chủ là chuyện thường; "-2 phút trước" trên một
  // tấm ảnh vừa đăng đọc như sản phẩm hỏng.
  assert.equal(batDauTu(truoc(-90 * GIAY), BAY_GIO), "vừa xong");
});

test("chuỗi không parse được thì im lặng, không in NaN", () => {
  assert.equal(batDauTu("hôm nọ", BAY_GIO), "");
  assert.equal(batDauTu("", BAY_GIO), "");
});

/* ------------------------------------------------------------ ngày +07 --- */

test("ngày đọc theo giờ Việt Nam, không theo múi giờ của máy", () => {
  // 2026-08-23T23:30:00+07:00 là 16:30 UTC ngày 23. Một máy ở New York đọc
  // theo giờ máy sẽ ra 12:30 ngày 23 — cùng ngày, nên ca đó không bắt được gì.
  // Mốc thật sự nguy hiểm là ngay sau nửa đêm giờ Việt Nam: 00:30 ngày 24 ở VN
  // là 17:30 ngày 23 ở UTC và 13:30 ngày 23 ở New York.
  assert.equal(ngayVietNam(Date.parse("2026-08-24T00:30:00+07:00")), "24/08/2026");
});

test("ca ngày chạy thật dưới TZ âm, không chỉ nói là đúng", () => {
  // `ngayVietNam` cộng offset rồi đọc bằng `getUTC*`, nên nó độc lập với TZ
  // theo cấu tạo. Ca này chạy nó ở một tiến trình có TZ âm để chứng minh điều
  // đó thay vì tin vào lập luận — cùng cách `ky-uc.test.mjs` làm.
  const ma = `
    import { ngayVietNam } from "${new URL("../dist-test/screens/widget/cau-chu.js", import.meta.url).pathname}";
    if (ngayVietNam(Date.parse("2026-08-24T00:30:00+07:00")) !== "24/08/2026") {
      throw new Error("sai ngày dưới TZ âm");
    }
  `;
  execFileSync(process.execPath, ["--input-type=module", "-e", ma], {
    env: { ...process.env, TZ: "America/New_York" },
  });
});

/* ------------------------------------------------------------ dòng tác giả --- */

test("dòng tác giả nối tên và thời điểm bằng dấu chấm giữa", () => {
  assert.equal(
    dongTacGia("Minh", truoc(5 * PHUT), BAY_GIO),
    "Minh · 5 phút trước",
  );
});

test("thời điểm đọc không được thì dấu chấm giữa đi theo, không để 'Minh · '", () => {
  // Dấu chấm giữa treo lủng lẳng đọc như một giá trị tải hỏng.
  assert.equal(dongTacGia("Minh", "hôm nọ", BAY_GIO), "Minh");
});

test("không có tên thì còn lại thời điểm, không để ' · vừa xong'", () => {
  assert.equal(dongTacGia("   ", truoc(0), BAY_GIO), "vừa xong");
});

/* ------------------------------------------------------------- từ chối --- */

test("403 nói bằng tiếng người, không lộ mã máy chủ", () => {
  const noi = loiWidget(403, "permission_denied");
  assert.match(noi, /thành viên/);
  assert.doesNotMatch(noi, /permission_denied|403/);
});

test("404 KHÔNG được nói nhóm có tồn tại hay không", () => {
  // Máy chủ cố ý không phân biệt "nhóm không có" với "bạn không ở trong nhóm";
  // một câu chữ ở đây nói ra sự khác biệt đó là trả lại đúng thứ nó giấu đi.
  const noi = loiWidget(404, "");
  assert.doesNotMatch(noi, /không tồn tại|chưa tồn tại|không có nhóm/);
});

test("mọi lời từ chối đều là tiếng Việt và không mang số trạng thái", () => {
  for (const [status, code] of [
    [0, ""],
    [401, ""],
    [403, "permission_denied"],
    [404, ""],
    [418, ""],
    [500, ""],
    [503, ""],
  ]) {
    const noi = loiWidget(status, code);
    assert.ok(noi.length > 10, `câu quá ngắn cho ${status}`);
    assert.doesNotMatch(noi, /[0-9]{3}/, `lộ mã trạng thái cho ${status}: ${noi}`);
    // Không em-dash: repo có cổng riêng bắt dấu này trong câu chữ người đọc.
    assert.doesNotMatch(noi, /—/, `dùng em-dash cho ${status}`);
  }
});

/* ------------------------------------------------------------ mô tả ảnh --- */

test("mô tả ảnh dùng caption khi có", () => {
  assert.equal(moTaAnh("Minh", "Sáng Đà Lạt, sương chưa tan"), "Sáng Đà Lạt, sương chưa tan");
});

test("không caption thì mô tả vẫn nói được đó là ảnh của ai", () => {
  // "ảnh" trống rỗng không giúp người dùng trình đọc màn hình biết gì thêm so
  // với việc không có ảnh nào.
  assert.equal(moTaAnh("Minh", null), "Ảnh Minh vừa đăng");
  assert.equal(moTaAnh("Minh", "   "), "Ảnh Minh vừa đăng");
});

/* --------------------------------------------- màn, đọc markup thật phát ra --- */

/* Trạng thái RỖNG — cái `quet-tab-url.mjs` không bao giờ chạm tới.
 *
 * Bộ quét trên URL chạy màn widget với một stub LUÔN có ảnh, nên "nhóm chưa có
 * tấm nào" không được máy nào vẽ ra. Nó lại đúng là trạng thái dễ sai nhất
 * trong ba: máy chủ trả 200 cho nó (cố ý, để không lộ khác biệt giữa "rỗng" và
 * "không được xem"), nên một client đọc nhầm thành lỗi sẽ hiện câu từ chối cho
 * một nhóm hoàn toàn bình thường.
 *
 * Đọc markup react-native-web thật sự phát ra chứ không đọc mã nguồn: `<Image>`
 * vẫn nằm nguyên trong file kể cả khi nhánh mount nó không bao giờ tới được,
 * nên một phép đọc nguồn ở đây không chứng minh gì. Đúng chỗ mù `anh.test.mjs`
 * đã ghi lại.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { KhungWidget } from "../dist-test/screens/widget/Widget.js";

const NHOM = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";
const TOI = "1aa00000-aaaa-4aaa-8aaa-0000a0000009";

function ve(photo) {
  return renderToStaticMarkup(
    React.createElement(KhungWidget, {
      wire: { context_id: NHOM, photo },
      nhom: NHOM,
      personId: TOI,
      bayGio: () => BAY_GIO,
    }),
  );
}

const CO_ANH = {
  memory_id: "5dd00000-dddd-4ddd-8ddd-0000d0000001",
  image_url: `/contexts/${NHOM}/photos/5dd00000-dddd-4ddd-8ddd-0000d0000002`,
  caption: "Sáng Đà Lạt, sương chưa tan",
  author_id: TOI,
  author_name: "Minh",
  created_at: new Date(BAY_GIO - 5 * PHUT).toISOString(),
};

test("photo: null là trạng thái RỖNG, không phải lỗi", () => {
  const html = ve(null);
  assert.match(html, /Nhóm chưa có ảnh nào/);
  // Không được mượn câu từ chối cho một câu trả lời 200.
  assert.doesNotMatch(html, /thành viên mới xem được|Chưa hiện được ảnh|Thử lại/);
});

test("khung rỗng vẫn giữ nguyên kích thước, không xẹp thành một dòng chữ", () => {
  // Một widget đổi hình dạng giữa "chưa có gì" và "có ảnh" là một widget nhảy
  // trên màn hình chính đúng lúc ai đó vừa đăng tấm đầu tiên.
  const rong = ve(null);
  const day = ve(CO_ANH);
  const tiSo = /aspect-ratio:\s*1/;
  assert.match(rong, tiSo, "khung rỗng mất tỉ lệ vuông");
  assert.match(day, tiSo, "khung có ảnh mất tỉ lệ vuông");
});

test("có ảnh thì in tên, thời điểm và caption", () => {
  const html = ve(CO_ANH);
  assert.match(html, /Minh · 5 phút trước/);
  assert.match(html, /Sáng Đà Lạt, sương chưa tan/);
});

/** Cắt đúng cây con của một thẻ, đếm thẻ mở/đóng cân bằng.
 *
 * Viết ra vì lượt đầu tôi dùng regex không tham `<div ...>.*?</div>` và nó
 * DỪNG ở `</div>` đầu tiên, đồng thời nuốt luôn `aria-label` của chính khung —
 * nên ca này ĐỎ với lý do sai: nó bắt được chuỗi caption nằm trong một thuộc
 * tính, chứ không bắt được chữ vẽ đè lên ảnh. Một ca đỏ vì phép đo của mình
 * hỏng đọc y hệt một ca đỏ vì sản phẩm hỏng.
 */
function cayCon(html, tuChiSo) {
  const bd = html.lastIndexOf("<div", tuChiSo);
  let i = bd;
  let sau = 0;
  while (i < html.length) {
    if (html.startsWith("<div", i)) sau += 1;
    else if (html.startsWith("</div>", i)) {
      sau -= 1;
      if (sau === 0) return html.slice(bd, i + 6);
    }
    i += 1;
  }
  throw new Error("không cắt được cây con cân bằng");
}

/** Chữ NHÌN THẤY được, bỏ hết thẻ và thuộc tính. */
function chuHienRa(html) {
  return html.replace(/<[^>]*>/g, "\u0000").split("\u0000").join(" ");
}

test("chữ KHÔNG nằm đè lên ảnh — nó nằm dưới, trên nền thẻ", () => {
  // `Anh` nói rõ: người gọi nào in chữ lên khung phải tự mang nền của mình, vì
  // mọi scrim trong app này được đo trên hình thay thế đã vẽ sẵn, còn một tấm
  // ảnh thật có thể sáng hơn bất kỳ cái nào trong số đó. Màn này chọn không
  // đánh cược, nên trong cây con của khung không được có chữ nào của tác giả.
  const html = ve(CO_ANH);
  const trongKhung = chuHienRa(cayCon(html, html.indexOf('role="img"')));
  assert.doesNotMatch(trongKhung, /Minh/, "tên tác giả bị vẽ đè lên ảnh");
  assert.doesNotMatch(trongKhung, /Sáng Đà Lạt/, "caption bị vẽ đè lên ảnh");
  // Và chúng có thật ở đâu đó ngoài khung — nếu không thì ca trên xanh vì màn
  // hình chẳng vẽ chữ nào cả.
  assert.match(chuHienRa(html), /Minh · 5 phút trước/);
  assert.match(chuHienRa(html), /Sáng Đà Lạt, sương chưa tan/);
});

test("khung ảnh có nhãn cho trình đọc màn hình; khung rỗng thì bị ẩn đi", () => {
  assert.match(ve(CO_ANH), /aria-label="Sáng Đà Lạt, sương chưa tan"/);
  // Không có ảnh thì `alt` rỗng, và `Anh` đưa cả khung ra khỏi cây trợ năng —
  // một khung trống tự xưng là "hình ảnh" thì tệ hơn là im lặng.
  assert.doesNotMatch(ve(null), /role="img"/);
});
