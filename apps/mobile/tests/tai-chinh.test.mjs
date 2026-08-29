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
