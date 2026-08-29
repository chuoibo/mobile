/* Màn Cá nhân: định dạng tiền, dấu, và cách nói khi máy chủ từ chối.
 *
 * Không có ca nào ở đây tính tiền, và đó là chủ ý. Ba con số trên màn tới nơi
 * đã cộng khớp sẵn từ sổ; nếu file này cộng trừ lại một cái thì sản phẩm có
 * hai phép tính cho cùng một bữa ăn. Cái đáng kiểm là phần dịch số thành chữ:
 * dấu phân cách, dấu +/-, và câu nói khi không đọc được sổ.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  loiTaiChinh,
  moTaGiaoDich,
  ngayNgan,
  tienCoDau,
  tienVnd,
} from "../dist-test/screens/ca-nhan/tai-chinh.js";

const movement = (over = {}) => ({
  obligation_id: "o1",
  direction: "out",
  amount_vnd: 350_000,
  counterparty_id: "p2",
  counterparty_name: "Trang",
  context_id: "c1",
  context_name: "Team Đà Lạt",
  occasion: "Lẩu nấm",
  occurred_at: "2026-05-20T12:30:00+07:00",
  ...over,
});

test("tiền nhóm bằng dấu chấm, kiểu Việt Nam", () => {
  assert.equal(tienVnd(5_860_000), "5.860.000đ");
  assert.equal(tienVnd(350_000), "350.000đ");
  assert.equal(tienVnd(0), "0đ");
  assert.equal(tienVnd(999), "999đ");
  assert.equal(tienVnd(1_000), "1.000đ");
});

test("không dùng Intl — Hermes thiếu ICU sẽ nhóm bằng dấu phẩy mà không báo", () => {
  // Ca này là lý do hàm được viết tay. Trên web, toLocaleString chạy đúng nên
  // lỗi vô hình; trên máy thật nó ra "5,860,000đ" — đọc như sản phẩm nước
  // ngoài, và không cổng nào bắt được vì web vẫn xanh.
  assert.ok(!tienVnd(5_860_000).includes(","));
});

test("dấu nằm ở direction, không nằm ở số", () => {
  assert.equal(tienCoDau(movement({ direction: "in" })), "+350.000đ");
  assert.equal(tienCoDau(movement({ direction: "out" })), "-350.000đ");
});

test("số tiền trong giao dịch luôn dương — mất dấu là biến khoản trả thành khoản thu", () => {
  for (const direction of ["in", "out"]) {
    const text = tienCoDau(movement({ direction }));
    assert.ok(!text.includes("--"), text);
    assert.match(text, /^[+-]\d/);
  }
});

test("ngày rút gọn dạng ngày/tháng", () => {
  assert.equal(ngayNgan("2026-05-20T12:30:00+07:00"), "20/05");
  assert.equal(ngayNgan("2026-01-02T00:00:00+07:00"), "02/01");
});

/* Ca này từng ĐỎ trên CI và XANH trên máy tôi, cùng một commit.
 *
 * `getDate()` trả lời theo múi giờ của MÁY, nên `2026-05-19T18:00:00Z` đọc ra
 * "20/05" ở +07 và "19/05" ở UTC — một khoản chi đổi ngày theo chỗ người xem
 * đang đứng. Ba mốc dưới đây đều rơi vào ngày HÔM SAU theo giờ Việt Nam nhưng
 * vẫn là hôm trước theo UTC.
 *
 * Đọc kỹ giới hạn của ca này: nó chỉ đỏ khi máy chạy test KHÔNG ở +07. Trên máy
 * một người Việt, bản dùng giờ máy và bản ghim giờ Việt Nam cho ra kết quả y
 * hệt nhau, nên ca này một mình sẽ để lọt. Ca ghim thật nằm ngay dưới.
 */
test("ngày là ngày ở Việt Nam, không phải ngày của máy đang xem", () => {
  assert.equal(ngayNgan("2026-05-19T18:00:00Z"), "20/05");
  assert.equal(ngayNgan("2026-01-01T17:00:00Z"), "02/01");
  // Giao thừa: 31/12 lúc 17:00Z đã là 01/01 ở Việt Nam.
  assert.equal(ngayNgan("2025-12-31T17:00:00Z"), "01/01");
});

/* Ca ghim: đỏ ở MỌI múi giờ máy, kể cả +07.
 *
 * Lỗi này đi lọt được vì người sửa và người review đều ngồi ở +07, nơi bản
 * hỏng và bản đúng cho ra cùng một chuỗi. Chỉ CI mới thấy — và tin vào CI để
 * bắt lỗi này nghĩa là mỗi lần tái phát phải tốn một vòng đẩy nhánh. Ca dưới
 * tự dời múi giờ của tiến trình nên nó đỏ ngay trên máy người sửa.
 *
 * Node đọc lại `process.env.TZ` khi đổi lúc đang chạy (đã kiểm trên v20). Nếu
 * một ngày nào đó nó thôi làm vậy thì mọi múi giờ dưới đây sẽ đọc thành múi giờ
 * của máy và ca sẽ XANH mà chẳng kiểm gì — nên bước đầu tiên là chứng minh cái
 * cần gạt còn sống, đúng kiểu đã dùng cho máy quét a11y.
 */
test("một mốc cho một ngày, dù máy người xem đứng ở múi giờ nào", () => {
  const MUI_GIO = [
    "UTC",
    "Asia/Ho_Chi_Minh", // +07, múi giờ của người dùng lẫn người viết test
    "Pacific/Kiritimati", // +14, xa nhất về phía đông
    "America/Los_Angeles", // -07/-08, qua bên kia ngày
    "Europe/London",
  ];
  const tzGoc = process.env.TZ;
  const iso = "2026-05-19T18:00:00Z"; // 01:00 sáng 20/05 giờ Việt Nam

  try {
    // Cần gạt còn sống chưa? Nếu đổi TZ không đổi được gì thì ca này vô nghĩa.
    const gioDocDuoc = new Set();
    for (const tz of MUI_GIO) {
      process.env.TZ = tz;
      gioDocDuoc.add(new Date(iso).getHours());
    }
    assert.ok(
      gioDocDuoc.size > 1,
      "đổi process.env.TZ không còn tác dụng — ca này không chứng minh được gì",
    );

    for (const tz of MUI_GIO) {
      process.env.TZ = tz;
      assert.equal(ngayNgan(iso), "20/05", `ngày đổi theo máy khi TZ=${tz}`);
    }
  } finally {
    if (tzGoc === undefined) delete process.env.TZ;
    else process.env.TZ = tzGoc;
  }
});

test("ngày hỏng trả chuỗi rỗng chứ không phải NaN/NaN", () => {
  assert.equal(ngayNgan("khong-phai-ngay"), "");
});

test("mô tả giao dịch nói ai, theo chiều tiền đi", () => {
  assert.equal(moTaGiaoDich(movement({ direction: "in" })), "Trang đã chuyển cho bạn");
  assert.equal(moTaGiaoDich(movement({ direction: "out" })), "Bạn đã trả Trang");
});

test("thiếu tên thì nói chung chung, không bao giờ in id ra màn hình", () => {
  const anon = movement({ counterparty_name: null });
  for (const direction of ["in", "out"]) {
    const text = moTaGiaoDich({ ...anon, direction });
    assert.ok(text.trim().length > 0);
    assert.ok(!text.includes("p2"), `lộ id: ${text}`);
  }
});

test("từ chối vì không phải chính chủ được nói bằng tiếng người", () => {
  assert.equal(
    loiTaiChinh(403, "not_your_finances"),
    "Chỉ chính chủ xem được phần tài chính này.",
  );
});

test("mỗi loại lỗi nói một câu khác nhau — 'có lỗi' không giúp ai sửa được gì", () => {
  const messages = new Set([
    loiTaiChinh(403, "not_your_finances"),
    loiTaiChinh(401, "authentication_required"),
    loiTaiChinh(500, ""),
    loiTaiChinh(418, ""),
  ]);
  assert.equal(messages.size, 4);
});

test("thông báo lỗi không chứa số tiền hay tên ai", () => {
  for (const status of [401, 403, 422, 500]) {
    const text = loiTaiChinh(status, status === 403 ? "not_your_finances" : "");
    assert.ok(!/\d{4,}/.test(text), `lộ số: ${text}`);
  }
});
