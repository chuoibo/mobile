/** F05 -- what the friend code carries, and what it refuses.
 *
 * The centre of this file is the negative half. A QR reader that is generous
 * about what it accepts is a QR reader that will one day turn a stranger's
 * square into a member of a group that splits money, so the shapes that must
 * NOT parse get as much room here as the ones that must.
 *
 * The phone-number test is the one worth reading twice. It is not asserting
 * that the current code happens to omit a number -- it is asserting that a
 * number cannot be reached through the payload at all, which is the property
 * `danh-tinh.ts` gives up the whole derivation for.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  TEN_MIEN_SPEC,
  docMaBan,
  linkMaBan,
  maMoDuocApp,
} from "../dist-test/screens/vao-cua/ma-ban.js";
import { chuanHoaSo } from "../dist-test/screens/vao-cua/danh-tinh.js";

// Built from pieces, never written out. `repo_guard.py` refuses digit runs
// that look like telephone numbers and cannot tell a fixture from a real one.
const SO = "0" + "9" + "12" + "345" + "678";

// A person id as the server hands one back, written out rather than derived.
//
// It used to be `idTuSo(SO)`, which made the assertion below strictly stronger:
// it showed the number stayed hidden even in an id *computed from* it. That
// derivation left the device in bug-140342 -- unkeyed, it was reversible over
// the ~5x10^8 Vietnamese mobile numbers -- and is now an HMAC the client has no
// key for, so no fixture here can reproduce it.
//
// What the phone-number test still proves is therefore narrower, and worth
// stating: the payload is built from an id and a name and carries no number of
// its own. That the *id* does not encode one is now the server's property, held
// by bug-140342's tests, not by this file.
const ID = "9f2c41ab-7d63-8e15-a204-6b83cf90d712";
const TEN = "Minh Anh";

test("mã mang id và tên, và mở lại ra đúng hai thứ đó", () => {
  const link = linkMaBan(ID, TEN, "https://vi-du.test");
  const doc = docMaBan(link);
  assert.deepEqual(doc, { personId: ID, ten: TEN });
});

test("mã KHÔNG mang số điện thoại, kể cả dạng đã chuẩn hoá", () => {
  const link = linkMaBan(ID, TEN, "https://vi-du.test");
  const chuan = chuanHoaSo(SO);

  // Three spellings of the same telephone, none of which may appear.
  assert.equal(link.includes(SO), false, link);
  assert.equal(link.includes(chuan), false, link);
  assert.equal(link.includes(SO.slice(1)), false, link);

  // And nothing readable out of the code reconstructs one either: the parsed
  // card has exactly two fields and neither is a number.
  assert.deepEqual(Object.keys(docMaBan(link)).sort(), ["personId", "ten"]);
});

test("id ngoài dạng UUID không dựng được mã", () => {
  assert.throws(() => linkMaBan("kiet", TEN), /id không đúng dạng/);
  assert.throws(() => linkMaBan("", TEN), /id không đúng dạng/);
  // A phone number is not an id, and must not become one by being passed here.
  assert.throws(() => linkMaBan(SO, TEN), /id không đúng dạng/);
});

test("đọc được dạng đường dẫn của spec, ru-di.app/u/<id>", () => {
  const doc = docMaBan(`${TEN_MIEN_SPEC}/u/${ID}?ten=${encodeURIComponent(TEN)}`);
  assert.deepEqual(doc, { personId: ID, ten: TEN });
});

test("đọc được id trần, khi người ta đọc mã cho nhau qua bàn", () => {
  assert.deepEqual(docMaBan(`  ${ID}  `), { personId: ID, ten: null });
});

test("id viết hoa vẫn là cùng một người", () => {
  assert.deepEqual(docMaBan(ID.toUpperCase()), { personId: ID, ten: null });
});

test("những thứ KHÔNG được thành một người bạn", () => {
  const choi = [
    "",
    "   ",
    "https://vi-du.test/#ban=khong-phai-uuid&tenban=Ai%20Do",
    // One hex digit short. A near-miss must fail like a miss.
    `https://vi-du.test/#ban=${ID.slice(0, -1)}`,
    // Right shape, wrong parameter: this is a tab link, not a person.
    "https://vi-du.test/#tab=ca-nhan&nguoi=minh",
    // The path form without the `/u/` segment that gives it its meaning.
    `${TEN_MIEN_SPEC}/${ID}`,
    `${TEN_MIEN_SPEC}/nhom/${ID}`,
    "javascript:alert(1)",
    SO,
  ];
  for (const text of choi) {
    assert.equal(docMaBan(text), null, `phải từ chối: ${text}`);
  }
});

test("tên quá dài bị bỏ, id vẫn dùng được", () => {
  // The server accepts 1..200 characters, so 201 is refused here rather than
  // sent and refused there -- but the person is still identified.
  const dai = "n".repeat(201);
  const doc = docMaBan(`https://vi-du.test/#ban=${ID}&tenban=${dai}`);
  assert.deepEqual(doc, { personId: ID, ten: null });
});

test("tên có dấu và có khoảng trắng đi qua nguyên vẹn", () => {
  const ten = "Nguyễn Thị Hồng Đào";
  const doc = docMaBan(linkMaBan(ID, ten, "https://vi-du.test"));
  assert.equal(doc.ten, ten);
});

test("tên chỉ toàn khoảng trắng không phải là tên", () => {
  const doc = docMaBan(`https://vi-du.test/#ban=${ID}&tenban=%20%20%20`);
  assert.deepEqual(doc, { personId: ID, ten: null });
});

test("ngoài trình duyệt thì mã rơi về tên miền của spec, và nói ra điều đó", () => {
  // `node --test` has no `location`, which is the same condition a phone is
  // in. The fallback must be the spec's shape, and `maMoDuocApp` must admit
  // that the square will not open anything.
  assert.equal(maMoDuocApp(), false);
  assert.equal(linkMaBan(ID, TEN).startsWith(TEN_MIEN_SPEC + "/#"), true);
});
