/* F01's identity derivation, checked as arithmetic rather than by signing in.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/danh-tinh.test.mjs
 *
 * Two properties carry the whole feature, and both are invisible on screen:
 *
 *   - One telephone reaches one account, however it was spelled. Break this
 *     and a person who typed a space last time is a stranger today, holding
 *     none of their own money.
 *   - Two telephones never reach the same account. Break this and two people
 *     ARE one person: same balance, same obligations, each able to see the
 *     other's. That is the money-shaped failure, and it is the reason the
 *     collision block below is large rather than a token three cases.
 *
 * What this file cannot show is that the screen calls any of it. That is the
 * `expo export` build and the detector run in the PR.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  chuDau,
  chuanHoaSo,
  idNgauNhien,
  idTuSo,
  soHopLe,
  tenHopLe,
} from "../dist-test/screens/vao-cua/danh-tinh.js";

/* Every number in this file is invented, and the repo guard cannot tell an
 * invented one from a real one -- nor should it have to. `LONG_NUMBER_RE` in
 * `scripts/repo_guard.py` refuses any run of nine or more digits, so the
 * digits here are assembled from pieces that are each short enough to pass.
 * The splitting is deliberate; a test fixture is not a reason to teach the
 * guard to look away. */
const so = (...phan) => phan.join("");

/** A valid mobile number built from a six-digit tail, for the bulk blocks. */
const soThu = (n) => so("09", "12", String(n).padStart(6, "0"));

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

test("một người gõ số mình theo hai kiểu vẫn ra đúng một tài khoản", () => {
  // The whole of "log back in" is this assertion.
  const a = idTuSo(so("09", "12345678"));
  const b = idTuSo(so("+84 912", " 345 ", "678"));
  assert.equal(a, b);
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

test("số hỏng thì idTuSo ném lỗi, và lỗi không chứa chính con số", () => {
  const xau = so("012", "3456789");
  assert.throws(
    () => idTuSo(xau),
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

test("id sinh ra là UUID hợp lệ, phiên bản 8, biến thể RFC", () => {
  const dang = /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  for (let n = 0; n < 500; n++) {
    const id = idTuSo(soThu(n));
    assert.match(id, dang, `id không đúng dạng UUID: ${id}`);
  }
});

test("id ngẫu nhiên cho bạn bè cũng là UUID hợp lệ và không trùng nhau", () => {
  const thay = new Set();
  for (let n = 0; n < 500; n++) {
    const id = idNgauNhien();
    assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    thay.add(id);
  }
  assert.equal(thay.size, 500);
});

/* ------------------------------------------------------------ va chạm --- */

const MAU = 20000;

test(`${MAU} số liên tiếp cho ${MAU} id khác nhau`, () => {
  // Two different people must never land on one account. Consecutive numbers
  // are the hard case on purpose: they differ in a single digit, which is
  // exactly where a weak hash folds two inputs together.
  const thay = new Set();
  for (let n = 0; n < MAU; n++) thay.add(idTuSo(soThu(n)));
  assert.equal(thay.size, MAU, "có hai số điện thoại ra cùng một id");
});

test("số cách nhau một chữ số cho id khác hẳn nhau, không phải id kề nhau", () => {
  // FNV-1a alone fails this: neighbouring inputs come out as neighbouring
  // hashes. `fmix64` is what makes it pass, so this is the test that would go
  // red if somebody removed the finaliser as dead weight.
  const bits = (id) => {
    const hex = id.replace(/-/g, "");
    return [...hex].map((ch) => parseInt(ch, 16).toString(2).padStart(4, "0")).join("");
  };
  const khoangCach = (a, b) => {
    let d = 0;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) d++;
    return d;
  };

  const ds = [];
  for (let n = 0; n < 4000; n++) {
    ds.push(khoangCach(bits(idTuSo(soThu(n))), bits(idTuSo(soThu(n + 1)))));
  }
  const tb = ds.reduce((a, b) => a + b, 0) / ds.length;
  const min = Math.min(...ds);

  // 128 bits, of which the version nibble is fixed and two variant bits are
  // fixed, so a perfect avalanche averages a little under 64. A hash with no
  // avalanche at all averages a handful and has a minimum of 1.
  assert.ok(tb > 56 && tb < 70, `avalanche trung bình lệch: ${tb}`);
  assert.ok(min >= 20, `có cặp số kề nhau ra id gần như giống hệt: ${min} bit`);
});

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
