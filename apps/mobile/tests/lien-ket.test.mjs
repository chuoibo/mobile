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

/* ---------------------------------------------------- kỷ niệm (F30/F35) --- */

test("vao=ky-niem mở thẳng tường kỷ niệm, không cần bấm qua menu [+]", () => {
  // The wall lives behind the [+] sheet, so without this a detector run, a
  // screenshot pass and an accessibility sweep all describe the opening screen
  // while claiming to describe the wall — and all three still exit 0.
  const d = docDiemDen("#vao=ky-niem&nguoi=minh");
  assert.equal(d.vao, "ky-niem");
  assert.equal(d.boQuaMoDau, true);
});

test("nhom=<uuid> đặt tên nhóm cho tường kỷ niệm", () => {
  const id = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";
  const d = docDiemDen(`#vao=ky-niem&nhom=${id}`);
  assert.equal(d.nhomId, id);
});

test("nhom gõ sai bị bỏ chứ không đi thẳng vào đường dẫn yêu cầu", () => {
  // This value is interpolated into a request path. A malformed one passed
  // through is the app writing somebody else's URL, so it has to become null
  // rather than "probably harmless".
  for (const bad of ["", "khong-phai-uuid", "../../etc/passwd", "1aa00000"]) {
    assert.equal(docDiemDen(`#vao=ky-niem&nhom=${bad}`).nhomId, null, bad);
  }
});

test("không có nhom thì để null — màn tự đi tìm nhóm demo", () => {
  assert.equal(docDiemDen("#vao=ky-niem").nhomId, null);
});

// F46. The place detail carries the check-in card, so a link that cannot name
// a place is a link that cannot reach the feature at all.

test("#dia-diem mở thẳng thẻ địa điểm, và tự chọn tab Khám phá", () => {
  const d = docDiemDen("#dia-diem=p-tiem-nuong-xom-lao");
  assert.equal(d.diaDiem, "p-tiem-nuong-xom-lao");
  // Naming a place without naming a tab must not land on the default tab with
  // the place quietly dropped.
  assert.equal(d.tab, "kham-pha");
  assert.equal(d.boQuaMoDau, true);
});

test("tab viết rõ thì thắng suy luận từ dia-diem", () => {
  const d = docDiemDen("#tab=ca-nhan&dia-diem=p-tiem-nuong-xom-lao");
  assert.equal(d.tab, "ca-nhan");
  assert.equal(d.diaDiem, "p-tiem-nuong-xom-lao");
});

test("dia-diem rỗng là không có, không phải một chỗ tên rỗng", () => {
  for (const hash of ["#dia-diem=", "#dia-diem=%20%20"]) {
    const d = docDiemDen(hash);
    assert.equal(d.diaDiem, null, hash);
    // And it must not drag the app past the opening screen on the strength of
    // a parameter that named nothing.
    assert.equal(d.boQuaMoDau, false, hash);
  }
});

test("không có dia-diem thì trường này là null", () => {
  assert.equal(docDiemDen("").diaDiem, null);
  assert.equal(docDiemDen("#tab=kham-pha").diaDiem, null);
});

/* ------------------------------------------------------- rd-fe-33: bản đồ --- */

test("#ban-do=1 mở bản đồ nhóm, và tự chọn tab Khám phá", () => {
  const d = docDiemDen("#ban-do=1");
  assert.equal(d.banDo, true);
  assert.equal(d.diemHen, false);
  assert.equal(d.tab, "kham-pha");
  // Vào thẳng: dừng ở màn mở đầu nghĩa là link im lặng không làm gì.
  assert.equal(d.boQuaMoDau, true);
});

test("#ban-do=hen đi thêm một màn nữa, tới Điểm hẹn", () => {
  const d = docDiemDen("#ban-do=hen");
  assert.equal(d.banDo, true);
  assert.equal(d.diemHen, true);
  assert.equal(d.tab, "kham-pha");
});

test("ban-do=0 và ban-do=false là KHÔNG, không phải 'có vì khoá tồn tại'", () => {
  // Đọc sự hiện diện của khoá thành 'có' là cách một báo cáo máy quét mô tả
  // nhầm màn mà vẫn thoát mã 0.
  for (const hash of ["#ban-do=0", "#ban-do=false"]) {
    const d = docDiemDen(hash);
    assert.equal(d.banDo, false, hash);
    assert.equal(d.diemHen, false, hash);
    assert.equal(d.tab, null, hash);
  }
});

test("tab viết rõ thì thắng suy luận từ ban-do", () => {
  const d = docDiemDen("#tab=ca-nhan&ban-do=1");
  assert.equal(d.tab, "ca-nhan");
  assert.equal(d.banDo, true);
});

test("không có ban-do thì hai cờ đều tắt", () => {
  const d = docDiemDen("#tab=kham-pha");
  assert.equal(d.banDo, false);
  assert.equal(d.diemHen, false);
});
