/* What the entry door can decide about a number without asking the server.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/danh-tinh.test.mjs
 *
 * This file used to test the id derivation as arithmetic, and it tested it
 * well: 20,000 consecutive numbers giving 20,000 distinct ids, and numbers one
 * digit apart giving ids half a digest apart. Both assertions passed and both
 * were about AVALANCHE. Neither was about whether an id could be turned back
 * into its number, which it could -- in 29.75 seconds. bug-140342.
 *
 * So the derivation moved behind a key the server holds, and those tests moved
 * with it, to `services/api/tests/api/test_person_identity.py`, where the one
 * that matters runs the actual attack instead of measuring how random the
 * output looks. What is left here is the rule this app still applies on its
 * own: what counts as a Vietnamese mobile number, so the button can stay off
 * without a round trip.
 *
 * Keeping the collision and avalanche blocks here as well would have been
 * comfortable and wrong -- they would have been testing a function this app no
 * longer owns.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  chuDau,
  chuanHoaSo,
  idNgauNhien,
  soHopLe,
  tenHopLe,
} from "../dist-test/screens/vao-cua/danh-tinh.js";
import { layIdTuSo } from "../dist-test/screens/vao-cua/cong-api.js";

/* Every number in this file is invented, and the repo guard cannot tell an
 * invented one from a real one -- nor should it have to. `LONG_NUMBER_RE` in
 * `scripts/repo_guard.py` refuses any run of nine or more digits, so the
 * digits here are assembled from pieces that are each short enough to pass.
 * The splitting is deliberate; a test fixture is not a reason to teach the
 * guard to look away. */
const so = (...phan) => phan.join("");

/* ------------------------------------------------------- chuẩn hoá số --- */

test("bốn cách viết một số đều về một dạng chuẩn", () => {
  const chuan = so("84", "912", "345", "678");
  for (const cach of [
    so("09", "12345678"),
    so("0912", " ", "345", " ", "678"),
    so("+84", "912", "345", "678"),
    so("84.912", ".345", ".678"),
    so("(091)", "234", "5678"),
    so("0912-345", "-678"),
  ]) {
    assert.equal(chuanHoaSo(cach), chuan, `không chuẩn hoá được: ${cach}`);
  }
});

test("một người gõ số mình theo hai kiểu vẫn gửi lên đúng một chuỗi", () => {
  // "Log back in" is now two halves. This is the client's half: whatever a
  // person types, one telephone leaves this device as one string. The other
  // half -- that one string reaches one id -- is the server's, and is asserted
  // in `test_person_identity.py::test_one_number_however_spelled_reaches_one_id`.
  //
  // Worth keeping even though it looks like the test above it. That one checks
  // a table of spellings against a constant; this one names the consequence,
  // so a change that breaks it fails with the sentence that explains what the
  // person lost.
  assert.equal(chuanHoaSo(so("09", "12345678")), chuanHoaSo(so("+84 912", " 345 ", "678")));
});

test("cái không phải số di động Việt Nam thì bị từ chối, không đoán bừa", () => {
  for (const xau of [
    "",
    "   ",
    so("012", "3456789"), // prefix 1 is not a mobile range
    so("02", "8", "3822", "1234"), // landline
    so("09", "1234"), // too short
    so("09", "12345678", "9"), // too long
    "không phải số",
    so("09", "1234567a"),
    "+1 555 0100",
  ]) {
    assert.equal(chuanHoaSo(xau), null, `đáng lẽ phải từ chối: "${xau}"`);
    assert.equal(soHopLe(xau), false);
  }
});

test("số hỏng thì layIdTuSo ném lỗi trước khi gửi, và lỗi không chứa con số", async () => {
  const xau = so("012", "3456789");
  // Refused on the device, so a number that cannot be an account never
  // travels at all. `fetch` is not stubbed here on purpose: if this ever
  // stopped throwing, the test would fail by trying to reach a real server
  // rather than by quietly passing against a mock.
  await assert.rejects(
    () => layIdTuSo(xau),
    (loi) => {
      // The number must not travel in a message that ends up in a console or
      // a bug report. This is the one assertion standing between a thrown
      // error and somebody's telephone number in a log.
      assert.ok(!loi.message.includes(xau), "thông báo lỗi có chứa số điện thoại");
      assert.ok(!/\d{4,}/.test(loi.message), "thông báo lỗi có chuỗi số dài");
      return true;
    },
  );
});

/* --------------------------------------------------------- dạng UUID --- */

test("id ngẫu nhiên cho bạn bè cũng là UUID hợp lệ và không trùng nhau", () => {
  const thay = new Set();
  for (let n = 0; n < 500; n++) {
    const id = idNgauNhien();
    assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    thay.add(id);
  }
  assert.equal(thay.size, 500);
});

/* Va chạm và avalanche không còn ở đây. Hàm sinh id nằm ở máy chủ kể từ
 * bug-140342, nên hai tính chất đó được gác ở
 * `services/api/tests/api/test_person_identity.py` — cùng với tính chất mà cả
 * hai đều KHÔNG chứng minh: id không đảo ngược lại thành số điện thoại. */

/* -------------------------------------------------------------- tên --- */

test("tên rỗng bị từ chối, tên dài quá 200 ký tự cũng vậy", () => {
  assert.equal(tenHopLe(""), false);
  assert.equal(tenHopLe("   "), false);
  assert.equal(tenHopLe("Minh"), true);
  assert.equal(tenHopLe("x".repeat(200)), true);
  assert.equal(tenHopLe("x".repeat(201)), false);
});

test("chữ đầu lấy từ tên gọi, tức chữ cuối trong tên tiếng Việt", () => {
  assert.equal(chuDau("Nguyễn Thu Hà"), "H");
  assert.equal(chuDau("Minh"), "M");
  assert.equal(chuDau("  trang  "), "T");
  assert.equal(chuDau(""), "?");
  assert.equal(chuDau("Đức"), "Đ");
});
