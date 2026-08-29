/* Điểm đến đọc từ URL: nhận đúng, và từ chối đoán.
 *
 * Hàm này quyết định app mở ra ở màn nào và với tư cách ai, mà "ai" thì màn Cá
 * nhân đem đi hỏi máy chủ về tiền. Nên ca đáng giá nhất ở đây không phải ca
 * nhận đúng — mà là ca gõ sai KHÔNG được lặng lẽ thành một người khác.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import { docDiemDen } from "../dist-test/navigation/lien-ket.js";
import { DEMO_PEOPLE } from "../dist-test/navigation/nhom-demo.js";

test("không có fragment thì không có điểm đến", () => {
  for (const hash of ["", "#"]) {
    const d = docDiemDen(hash);
    assert.equal(d.tab, null);
    assert.equal(d.nguoi, null);
    assert.equal(d.boQuaMoDau, false);
  }
});

test("tab hợp lệ mở thẳng vào tab đó", () => {
  const d = docDiemDen("#tab=ca-nhan");
  assert.equal(d.tab, "ca-nhan");
  assert.equal(d.boQuaMoDau, true);
});

test("tab lạ bị bỏ, app mở bình thường chứ không mở màn trắng", () => {
  const d = docDiemDen("#tab=khong-co-tab-nay");
  assert.equal(d.tab, null);
  assert.equal(d.boQuaMoDau, false);
});

test("nguoi hợp lệ vào đúng người đó, kèm personId thật", () => {
  const d = docDiemDen("#tab=ca-nhan&nguoi=minh");
  assert.equal(d.nguoi.id, "minh");
  assert.equal(d.nguoi.personId, DEMO_PEOPLE.find((p) => p.id === "minh").personId);
});

test("slug người gõ sai KHÔNG được thành người khác — đây là ví tiền của ai đó", () => {
  // Ca quan trọng nhất file này. Đoán "min" thành "minh" nghĩa là mở sổ tiền
  // của một người khác cho người đang cầm máy xem.
  for (const slug of ["min", "MINH", "minh ", "khong-ai", ""]) {
    const d = docDiemDen(`#tab=ca-nhan&nguoi=${encodeURIComponent(slug)}`);
    assert.equal(d.nguoi, null, `"${slug}" bị đoán thành người`);
  }
});

test("chỉ có nguoi, không có tab: vẫn vào app, ở tab mặc định", () => {
  const d = docDiemDen("#nguoi=trang");
  assert.equal(d.tab, null);
  assert.equal(d.nguoi.id, "trang");
  assert.equal(d.boQuaMoDau, true);
});

test("mọi người trong nhóm demo đều mở được bằng link", () => {
  for (const p of DEMO_PEOPLE) {
    const d = docDiemDen(`#tab=ca-nhan&nguoi=${p.id}`);
    assert.equal(d.nguoi.personId, p.personId, `${p.id} không mở được`);
  }
});

test("fragment rác không làm hàm ném lỗi", () => {
  for (const hash of ["#=", "#&&&", "#tab", "#%%%", "#tab=ca-nhan&tab=len-plan"]) {
    assert.doesNotThrow(() => docDiemDen(hash), hash);
  }
});

/* ----------------------------------------------- màn vào cửa (F01/F03/F04) --- */

test("#vao=dang-ky mở màn đăng ký, nhưng KHÔNG tự bỏ qua màn mở đầu", () => {
  const d = docDiemDen("#vao=dang-ky");
  assert.equal(d.vao, "dang-ky");
  // The registration screen writes to `people`. A link that walked somebody
  // straight into it would be a link that starts creating an account.
  assert.equal(d.boQuaMoDau, false);
});

test("#vao=nhom vào thẳng màn nhóm trong vỏ tab", () => {
  const d = docDiemDen("#vao=nhom&nguoi=minh");
  assert.equal(d.vao, "nhom");
  assert.equal(d.nguoi.id, "minh");
  assert.equal(d.boQuaMoDau, true);
});

test("tên màn lạ bị bỏ qua chứ không mở màn trắng", () => {
  for (const hash of ["#vao=khong-co-man-nay", "#vao=", "#vao=DANG-KY"]) {
    assert.equal(docDiemDen(hash).vao, null, hash);
  }
});

test("không có fragment thì không có màn vào cửa nào", () => {
  assert.equal(docDiemDen("").vao, null);
  assert.equal(docDiemDen("#tab=ca-nhan").vao, null);
});
