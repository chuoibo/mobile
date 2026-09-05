/**
 * The personalization step, now that it leaves the phone (M11, ADR-0019).
 *
 * What these prove: the wire shape read back defensively, the sentence under
 * the button being true in both states, and the summary line the Cá nhân row
 * shows. What they do not prove: that the server stores any of it -- that is
 * `services/api/tests/postgres/test_interests_postgres.py`.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  cauLuuTru,
  daNoiGi,
  doc,
  tomTat,
} from "../dist-test/rudi/nguoi/so-thich-song.js";

test("đọc hình dạng máy chủ: thiếu trường là «chưa nói gì», không phải đoán", () => {
  assert.deepEqual(doc({}), { muc: [], khoang: null });
  assert.deepEqual(doc({ interests: null, budget_band: null }), { muc: [], khoang: null });
});

test("thứ tự là của từ vựng, không phải của thứ tự máy chủ trả", () => {
  const da = doc({ interests: ["cafe", "an-uong"], budget_band: "vua-phai" });
  assert.deepEqual(da.muc, ["an-uong", "cafe"]);
  assert.equal(da.khoang, "vua-phai");
});

test("một từ bản dựng này chưa biết bị bỏ, không in ra thành id", () => {
  // Từ vựng máy chủ có thể dài ra trước khi app cập nhật. Một chip ghi
  // «du-thuyen» trên màn tệ hơn một chip ít đi.
  const da = doc({ interests: ["cafe", "du-thuyen"] });
  assert.deepEqual(da.muc, ["cafe"]);
});

test("mức chi không còn dùng đọc thành «chưa chọn», không thành lỗi", () => {
  assert.equal(doc({ budget_band: "sang-chanh" }).khoang, null);
});

test("chọn không gì cả khác với chưa nói gì", () => {
  assert.equal(daNoiGi({ muc: [], khoang: null }), false);
  assert.equal(daNoiGi({ muc: [], khoang: "tiet-kiem" }), true);
  assert.equal(daNoiGi({ muc: ["cafe"], khoang: null }), true);
});

test("câu dưới nút nói đúng sự thật ở cả hai trạng thái", () => {
  // Giữ nguyên câu cũ («Chưa gửi lên máy chủ») sau khi đã nối route là đúng
  // cái lời nói dối mà luật vỏ sinh ra để cấm; nói «đã lưu» cho người chưa
  // đăng nhập là ảnh trong gương của nó.
  assert.match(cauLuuTru(true), /lưu vào tài khoản/);
  assert.doesNotMatch(cauLuuTru(true), /Chưa gửi/);
  assert.match(cauLuuTru(false), /Đăng nhập/);
  assert.match(cauLuuTru(false), /chỉ nằm trên máy này/);
});

test("dòng tóm tắt ở Cá nhân: tên chứ không phải id, và cắt có nói", () => {
  assert.equal(tomTat({ muc: [], khoang: null }), "Chưa chọn");
  assert.equal(tomTat({ muc: ["cafe"], khoang: "vua-phai" }), "Cafe · 100K–250K");
  const nhieu = tomTat({ muc: ["an-uong", "cafe", "nightlife", "outdoor"], khoang: null });
  assert.equal(nhieu, "Ăn uống, Cafe, Nightlife +1");
});

test("chỉ chọn mức chi mà không chọn sở thích vẫn nói được", () => {
  assert.equal(tomTat({ muc: [], khoang: "tiet-kiem" }), "Chưa chọn sở thích · Dưới 100K");
});
