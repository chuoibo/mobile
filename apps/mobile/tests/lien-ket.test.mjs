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
