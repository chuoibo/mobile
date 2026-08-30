/** F01.03 -- what the personalization step promises, held to.
 *
 * Four claims are worth a test here, and they are the four a screenshot cannot
 * settle:
 *
 *   1. The budget presets are integer đồng and tile without overlapping. Law 1
 *      of this repo is integer đồng including intermediate values, and a band
 *      catalogue is where a `225000.5` would enter by way of somebody
 *      "simplifying" two bounds into one midpoint.
 *   2. Skipping is a real answer. The header draws a "Bỏ qua", so `null` has to
 *      survive all the way out rather than being back-filled with a default
 *      band by anything downstream.
 *   3. Every permission outcome has a sentence. The mockup asks for pre-prompt,
 *      granted and denied; this build adds a third, honest outcome, and a
 *      screen that reached an outcome with no line to print would be a switch
 *      that did nothing.
 *   4. Selection order does not leak into the value.
 *
 * Nothing here renders React. The screen imports these and only these for its
 * data, so the properties below are the ones the screen cannot violate without
 * changing this file.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  cauVeDanhBa,
  doiMuc,
  ghiNhoSoThich,
  KHONG_CO_DANH_BA,
  khoangTheoId,
  NGAN_SACH,
  quenSoThich,
  SO_THICH,
  SO_THICH_RONG,
  soThichDaChon,
} from "../dist-test/screens/vao-cua/so-thich.js";

test("ngân sách là số nguyên đồng, và ba khoảng lợp kín không chồng nhau", () => {
  assert.ok(NGAN_SACH.length >= 3, `chỉ có ${NGAN_SACH.length} khoảng`);

  for (const k of NGAN_SACH) {
    assert.ok(Number.isInteger(k.tu), `${k.id}.tu = ${k.tu} không phải số nguyên`);
    assert.ok(
      k.den === null || Number.isInteger(k.den),
      `${k.id}.den = ${k.den} không phải số nguyên`,
    );
    if (k.den !== null) {
      assert.ok(k.den > k.tu, `${k.id} có cận trên ${k.den} không lớn hơn cận dưới ${k.tu}`);
    }
  }

  // Cận trên của khoảng trước phải đúng bằng cận dưới của khoảng sau. Hở một
  // đồng thì có số tiền không thuộc khoảng nào; chồng một đồng thì có số tiền
  // thuộc hai khoảng, và cả hai đều làm gợi ý trả lời khác nhau cho cùng bữa ăn.
  for (let i = 1; i < NGAN_SACH.length; i += 1) {
    assert.equal(
      NGAN_SACH[i].tu,
      NGAN_SACH[i - 1].den,
      `khoảng "${NGAN_SACH[i - 1].id}" kết ở ${NGAN_SACH[i - 1].den} nhưng "${NGAN_SACH[i].id}" mở ở ${NGAN_SACH[i].tu}`,
    );
  }
});

test("bỏ trống ngân sách vẫn là một câu trả lời, không bị điền hộ", () => {
  assert.equal(khoangTheoId(null), null);
  // Một id lạ (phiên cũ, hoặc khoảng đã bị bỏ) không được rơi về khoảng đầu.
  assert.equal(khoangTheoId("khoang-khong-ton-tai"), null);
  assert.equal(SO_THICH_RONG.khoang, null);
  assert.deepEqual(SO_THICH_RONG.muc, []);
  assert.equal(SO_THICH_RONG.danhBa, null);

  const co = khoangTheoId(NGAN_SACH[1].id);
  assert.equal(co?.id, NGAN_SACH[1].id, "id có thật thì phải tra ra đúng khoảng");
});

test("mọi kết quả xin quyền danh bạ đều có một câu để hiện lên màn", () => {
  for (const ket of ["cho-phep", "tu-choi", "chua-co"]) {
    const cau = cauVeDanhBa(ket);
    assert.equal(typeof cau, "string", `${ket} không có câu`);
    assert.ok(cau.trim().length > 0, `${ket} trả câu rỗng`);
    // Không lộ mã lỗi tiếng Anh của máy ra chữ người dùng đọc.
    assert.ok(
      !/[a-z]_[a-z]/.test(cau),
      `câu cho "${ket}" có vẻ chứa mã máy: ${cau}`,
    );
  }

  // Ba câu phải khác nhau. Ba nhánh cùng một câu là ba nhánh không phân biệt
  // được, và người bấm "Bật đồng bộ" sẽ đọc đúng thứ người bấm "Để sau" đọc.
  const cac = new Set(["cho-phep", "tu-choi", "chua-co"].map(cauVeDanhBa));
  assert.equal(cac.size, 3, "hai kết quả trở lên dùng chung một câu");
});

test("bản dựng này nói thật là chưa đọc danh bạ", async () => {
  // Đường mặc định KHÔNG được trả "cho-phep". Nếu ai đó nối quyền thật thì
  // phải thay hàm này, và ca đỏ ở đây là lời nhắc sửa cả câu chữ lẫn test.
  assert.equal(await KHONG_CO_DANH_BA(), "chua-co");
});

test("thứ tự bấm không lọt vào giá trị", () => {
  const a = doiMuc(doiMuc([], "cafe"), "an-uong");
  const b = doiMuc(doiMuc([], "an-uong"), "cafe");
  assert.deepEqual(a, b, "cùng một tập sở thích mà ra hai giá trị khác nhau");

  // Và đúng thứ tự của bảng, không phải thứ tự ngón tay.
  const thuTu = SO_THICH.map((m) => m.id);
  assert.ok(thuTu.indexOf(a[0]) < thuTu.indexOf(a[1]), `${JSON.stringify(a)} không theo thứ tự bảng`);

  // Bấm lại thì bỏ chọn.
  assert.deepEqual(doiMuc(a, "cafe"), ["an-uong"]);
  assert.deepEqual(doiMuc(doiMuc(a, "cafe"), "an-uong"), []);
});

test("chưa tới bước này khác với tới rồi mà không chọn gì", () => {
  quenSoThich();
  assert.equal(soThichDaChon(), null, "chưa tới thì phải là null");

  ghiNhoSoThich(SO_THICH_RONG);
  const sau = soThichDaChon();
  assert.notEqual(sau, null, "tới rồi mà bỏ qua thì không còn là null");
  assert.deepEqual(sau?.muc, []);
  assert.equal(sau?.khoang, null);

  quenSoThich();
});

test("mỗi sở thích có nhãn đọc được, và id không trùng", () => {
  assert.ok(SO_THICH.length >= 6, `chỉ có ${SO_THICH.length} sở thích`);
  const ids = new Set(SO_THICH.map((m) => m.id));
  assert.equal(ids.size, SO_THICH.length, "có id sở thích bị trùng");
  for (const m of SO_THICH) {
    assert.ok(m.nhan.trim().length > 0, `${m.id} không có nhãn`);
    // Nhãn là tên đọc được, hình là trang trí. Nhãn mang hình nghĩa là tên
    // đọc lên sẽ có cả pictograph.
    assert.ok(!m.nhan.includes(m.hinh), `${m.id} nhét hình vào nhãn`);
  }
});
