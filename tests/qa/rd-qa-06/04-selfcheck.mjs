/* rd-qa-06 · ĐỐI CHỨNG — chứng minh bộ đo còn sống TRƯỚC khi tin bất kỳ số 0 nào.
 *
 * Mọi kết luận "không rò rỉ", "Σ đúng", "QR đúng số tiền" ở 02 và 03 đều dựa
 * trên ba hàm trong lib.mjs. Nếu ba hàm đó không thể đỏ, thì "0 vấn đề" ở kia
 * chỉ là một hàm luôn trả về mảng rỗng. File này lấy CHÍNH dữ liệu thật vừa đo
 * được, trồng lỗi vào, rồi đòi hàm phải bắt được — và cũng đòi dữ liệu sạch
 * phải cho ra 0, để một hàm "luôn đỏ" cũng không lọt.
 *
 * Chạy bằng: node --test 04-selfcheck.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { sumProblems, leakProblems, qrProblems } from "./lib.mjs";

// Dữ liệu thật, chép từ lần chạy 02/03 trên commit đang đo.
const ROWS = [
  { who: "Hà (trả trước)", amount: 160001 },
  { who: "Nam", amount: 160000 },
  { who: "Linh", amount: 160000 },
];
const TONG = 480001;
const PAYLOAD =
  "00020101021238580010A0000007270128000697041801140000000000TEST0208QRIBFTTA53037045406160000" +
  "5802VN62150811TT 8928854c6304672E";
const GUEST_PLAIN =
  "Chi tiết khoản cần gửi Hà đã ghi Phần của Linh trong lẩu gà lá é 160.000 đ chạm để chép " +
  "Chuyển tới NGUOI UNG TIEN · BIDV Chỉ hiển thị phần của bạn.";
const GUEST_ARGS = {
  who: "Linh", plain: GUEST_PLAIN, html: "<html>" + GUEST_PLAIN + "</html>",
  ownAmount: "160.000", otherNames: ["Nam"], forbiddenAmounts: ["480.001", "160.001"],
};

test("dữ liệu THẬT cho ra 0 vấn đề (nếu không, bộ đo luôn đỏ và cũng vô dụng)", () => {
  assert.deepEqual(sumProblems(ROWS, TONG, 480001), []);
  assert.deepEqual(leakProblems(GUEST_ARGS), []);
  assert.deepEqual(qrProblems(PAYLOAD, [PAYLOAD], "160000"), []);
});

test("trồng lỗi tiền: một dòng lệch 1đ thì Σ phải đỏ", () => {
  const mutant = ROWS.map((r, i) => (i === 1 ? { ...r, amount: r.amount - 1 } : r));
  const found = sumProblems(mutant, TONG, 480001);
  assert.ok(found.some((f) => /LUẬT TIỀN 2 vỡ/.test(f)), "Σ lệch 1đ mà không ai kêu: " + JSON.stringify(found));
});

test("trồng lỗi tiền: tổng trên màn khác số đã gõ thì phải đỏ", () => {
  assert.ok(sumProblems(ROWS, TONG, 480000).some((f) => /≠ số đã gõ/.test(f)));
});

test("trồng lỗi tiền: phân bổ không phải số nguyên đồng thì phải đỏ", () => {
  const mutant = [{ ...ROWS[0], amount: 160000.5 }, ROWS[1], ROWS[2]];
  assert.ok(sumProblems(mutant, TONG, 480001).some((f) => /số nguyên đồng/.test(f)));
});

test("trồng rò rỉ: tổng của cả nhóm lọt lên trang khách thì phải đỏ", () => {
  const leaked = { ...GUEST_ARGS, plain: GUEST_PLAIN + " Cả nhóm: 480.001 đ" };
  assert.ok(leakProblems(leaked).some((f) => /RÒ RỈ.*480\.001/.test(f)));
});

test("trồng rò rỉ: tên người khác lọt lên trang khách thì phải đỏ", () => {
  const leaked = { ...GUEST_ARGS, plain: GUEST_PLAIN + " Nam còn nợ." };
  assert.ok(leakProblems(leaked).some((f) => /tên người khác "Nam"/.test(f)));
});

test("trồng rò rỉ: trường cấm trong HTML thì phải đỏ", () => {
  const leaked = { ...GUEST_ARGS, html: GUEST_ARGS.html + '<!--{"group_balance":1}-->' };
  assert.ok(leakProblems(leaked).some((f) => /group_balance/.test(f)));
});

test("TRANG TRẮNG không được đọc thành 'không rò rỉ'", () => {
  // Đây là cái bẫy rd-qa-05 ghi lại: chỉ khẳng định cái-không-có thì một trang
  // trắng pass sạch sẽ. Hàm phải kêu vì KHÔNG thấy phần của chính người này.
  const blank = { ...GUEST_ARGS, plain: "", html: "" };
  assert.ok(leakProblems(blank).some((f) => /KHÔNG thấy số tiền của chính họ/.test(f)));
});

test("trang in tiền ở ĐỊNH DẠNG khác cũng phải bị bắt, không được pass rỗng", () => {
  const other = { ...GUEST_ARGS, plain: GUEST_PLAIN.replace("160.000", "160,000") };
  assert.ok(leakProblems(other).some((f) => /KHÔNG thấy số tiền của chính họ/.test(f)));
});

test("trồng lỗi QR: không giải mã được thì phải đỏ", () => {
  assert.ok(qrProblems("", [PAYLOAD], "160000").some((f) => /KHÔNG giải mã được/.test(f)));
});

test("trồng lỗi QR: số tiền trong mã khác số trên màn thì phải đỏ", () => {
  const swapped = PAYLOAD.replace("5406" + "160000", "5406" + "990000");
  assert.ok(qrProblems(swapped, [swapped], "160000").some((f) => /mã hoá số tiền 990000/.test(f)));
});

test("trồng lỗi QR: mã lạ không khớp payload máy chủ thì phải đỏ", () => {
  assert.ok(qrProblems("0002" + "0101" + "0212" + "6304" + "1234", [PAYLOAD], "160000")
    .some((f) => /KHÁC payload máy chủ/.test(f)));
});
