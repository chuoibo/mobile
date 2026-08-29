/* F34. Spending against the budget, and whether the right number is on screen.
 *
 * This file is deliberately in two halves, because the two halves fail for
 * different reasons and only one of them is the reason this feature exists.
 *
 * The first half tests `doNganSach` as arithmetic: integers in, integers out,
 * over is over. A mutation there is caught by a function-level assertion.
 *
 * The second half renders `TheBuoi` through react-native-web -- the same
 * substitution Expo's web build performs -- and reads the emitted markup. It is
 * there because a function returning `6000000` proves nothing about what a
 * person sees. The failure this product cannot afford is a wrong amount ARRIVING
 * ON THE CARD, and a component that formats with the wrong helper, multiplies a
 * second time on the way out, or drops the block entirely passes every
 * assertion in the first half. rd-fe-15 learned this the same way: the reading
 * has to be measured where the person reads it.
 *
 * The mutation this file is built to catch, named out loud so nobody has to
 * infer it: change `tongDuKien` to `budget * headcount * 1000`, or format the
 * spend with a helper that is off by a factor of a thousand, and the assertions
 * below go red ON THE RENDERED STRING -- 1.200.000 x 5 stops reading 6.000.000đ
 * and grows three more digits, which is exactly what a person would otherwise
 * have had to notice unaided.
 *
 * What it does not prove: that iOS and Android draw the block, that it is
 * legible at a real size, or that "Vượt ngân sách" is the right wording. The
 * first is a different bridge; the other two are `imp detect` and a person.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  doNganSach,
  nguonDaTieu,
  nhanDaTieu,
  nhanKetLuan,
  tienVnd,
} from "../dist-test/screens/len-plan/ngan-sach.js";
import { tongDuKien } from "../dist-test/screens/len-plan/buoi-di.js";
import { TheBuoi } from "../dist-test/screens/len-plan/LenPlan.js";

/** 1.200.000đ per person, 5 people. The budget is 6.000.000đ, and every
 *  number in this file is chosen so that a x1000 slip is unmistakable. */
const BUOI = {
  id: "b1",
  context_id: "c1",
  created_by_id: "p1",
  title: "Đà Lạt cuối tuần",
  starts_on: "2026-09-05",
  ends_on: "2026-09-07",
  headcount: 5,
  budget_per_person_vnd: 1_200_000,
  created_at: "2026-08-29T10:00:00Z",
  stops: [],
};

/* ------------------------------------------------------ the arithmetic --- */

test("ngân sách là số người nhân ngân sách mỗi người, số nguyên", () => {
  assert.equal(tongDuKien(1_200_000, 5), 6_000_000);
  assert.ok(Number.isInteger(tongDuKien(1_200_000, 5)));
});

test("tiêu dưới ngân sách thì còn lại là hiệu hai số nguyên", () => {
  const y = doNganSach(BUOI, { kind: "co", vnd: 4_500_000 });
  assert.equal(y.kind, "trong");
  assert.equal(y.nganSachVnd, 6_000_000);
  assert.equal(y.daTieuVnd, 4_500_000);
  assert.equal(y.conLaiVnd, 1_500_000);
  assert.ok(Number.isInteger(y.conLaiVnd));
});

test("tiêu đúng bằng ngân sách vẫn là trong ngân sách, không phải vượt", () => {
  const y = doNganSach(BUOI, { kind: "co", vnd: 6_000_000 });
  assert.equal(y.kind, "trong");
  assert.equal(y.conLaiVnd, 0);
});

test("vượt một đồng đã là vượt, và mức vượt là hiệu đúng", () => {
  const y = doNganSach(BUOI, { kind: "co", vnd: 6_000_001 });
  assert.equal(y.kind, "vuot");
  assert.equal(y.vuotVnd, 1);
});

test("vượt nhiều thì mức vượt vẫn là hiệu hai số nguyên", () => {
  const y = doNganSach(BUOI, { kind: "co", vnd: 7_200_000 });
  assert.equal(y.kind, "vuot");
  assert.equal(y.vuotVnd, 1_200_000);
  assert.ok(Number.isInteger(y.vuotVnd));
});

/* ----------------------------------------- absent is not the same as 0 --- */

test("chuyến chưa xong thì không có số đã tiêu, và lý do nói đúng", () => {
  const y = doNganSach(BUOI, { kind: "chua-xong" });
  assert.equal(y.kind, "chua-co-so");
  assert.equal(y.vi, "chua-xong");
  assert.equal(y.nganSachVnd, 6_000_000);
  assert.match(nhanKetLuan(y), /chưa xong/);
});

test("đọc sổ hỏng thì nói là chưa đọc được, không nói là chuyến chưa xong", () => {
  const y = doNganSach(BUOI, { kind: "khong-doc-duoc" });
  assert.equal(y.kind, "chua-co-so");
  assert.equal(y.vi, "khong-doc-duoc");
  // The wrong sentence here sends somebody to look at the trip's dates when
  // the real problem is the request.
  assert.match(nhanKetLuan(y), /Chưa đọc được/);
  assert.doesNotMatch(nhanKetLuan(y), /chưa xong/);
});

test("sổ trả 0đ khác hẳn sổ không trả gì", () => {
  const khong = doNganSach(BUOI, { kind: "chua-xong" });
  const rong = doNganSach(BUOI, { kind: "co", vnd: 0 });
  assert.equal(khong.kind, "chua-co-so");
  assert.equal(rong.kind, "trong");
  assert.equal(rong.daTieuVnd, 0);
  // "Đã tiêu 0đ" is a measurement. The other one must not claim to be one.
  assert.doesNotMatch(nhanDaTieu(khong), /Đã tiêu/);
  assert.match(nhanDaTieu(rong), /Đã tiêu 0đ/);
});

test("số đã tiêu không phải số nguyên không dương thì bị hạ xuống không có số", () => {
  for (const xau of [1.5, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
    const y = doNganSach(BUOI, { kind: "co", vnd: xau });
    assert.equal(y.kind, "chua-co-so", `giá trị ${xau} không được thành nhãn tiền`);
  }
});

test("nguonDaTieu phân biệt thiếu trong bản đồ với đọc hỏng", () => {
  const theo = new Map([["b1", 4_500_000]]);
  assert.deepEqual(nguonDaTieu({ kind: "xong", theo }, "b1"), { kind: "co", vnd: 4_500_000 });
  assert.deepEqual(nguonDaTieu({ kind: "xong", theo }, "b2"), { kind: "chua-xong" });
  assert.deepEqual(nguonDaTieu({ kind: "loi" }, "b1"), { kind: "khong-doc-duoc" });
});

/* ---------------------------------------------------- readable amounts --- */

test("tiền hiện ra đọc được, không phải một dãy chữ số liền", () => {
  assert.equal(tienVnd(1_200_000), "1.200.000đ");
  assert.equal(tienVnd(6_000_000), "6.000.000đ");
  assert.equal(tienVnd(0), "0đ");
});

/* ------------------------------------ the number a person actually sees --- */

/** Markup with tags stripped, which is what a person actually reads. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

function theBuoi(nguon) {
  return words(React.createElement(TheBuoi, { buoi: BUOI, nguon, onMo: () => {} }));
}

test("con số đã tiêu và ngân sách nằm trong markup, đúng từng chữ số", () => {
  const doc = theBuoi({ kind: "co", vnd: 4_500_000 });
  // The whole sentence, not two numbers found separately. A card that renders
  // the right digits under the wrong labels is still wrong.
  assert.ok(
    doc.includes("Đã tiêu 4.500.000đ / ngân sách 6.000.000đ"),
    `câu đã tiêu không có trên markup: ${doc}`,
  );
  assert.ok(doc.includes("Còn 1.500.000đ"), `số còn lại không có trên markup: ${doc}`);
});

test("nhân sai một bậc thì con số sai hiện ra ở đây, không chỉ ở hàm", () => {
  // This is the assertion the acceptance criterion names. `tongDuKien` is
  // 1.200.000 x 5; multiply it by a thousand anywhere between the model and the
  // markup and the card grows three digits. Pinning the exact rendered string
  // is what makes that visible: the inflated amount does not contain
  // "6.000.000đ", because the thousands separators all land somewhere else.
  const doc = theBuoi({ kind: "co", vnd: 4_500_000 });
  assert.ok(doc.includes("ngân sách 6.000.000đ"), `ngân sách sai trên markup: ${doc}`);
  // Built by multiplying rather than typed out, so the expected wrong value is
  // tied to the slip it describes instead of to a digit string somebody has to
  // recount. It also keeps a ten-digit run out of the source, which repo-guard
  // reads as a possible account number and refuses.
  for (const dung of [6_000_000, 4_500_000]) {
    assert.ok(
      !doc.includes(tienVnd(dung * 1000)),
      `một con số bị nhân thừa một bậc đã lên tới màn hình: ${doc}`,
    );
  }
  // The per-person reference is on the same card and is the other place a
  // x1000 slip would surface.
  assert.ok(doc.includes("1.200.000đ/người"), `ngân sách mỗi người sai trên markup: ${doc}`);
});

test("vượt ngân sách thì lời cảnh báo có trên markup, bằng chữ chứ không chỉ bằng màu", () => {
  const doc = theBuoi({ kind: "co", vnd: 7_200_000 });
  assert.ok(doc.includes("Đã tiêu 7.200.000đ / ngân sách 6.000.000đ"), doc);
  assert.ok(doc.includes("Vượt ngân sách"), `không có chữ cảnh báo: ${doc}`);
  // The amount over, written out. Colour carries nothing into a screenshot.
  assert.ok(doc.includes("Vượt 1.200.000đ"), `không có mức vượt bằng đồng: ${doc}`);
});

test("cảnh báo chỉ xuất hiện khi thật sự vượt", () => {
  assert.ok(!theBuoi({ kind: "co", vnd: 6_000_000 }).includes("Vượt ngân sách"));
  assert.ok(!theBuoi({ kind: "co", vnd: 4_500_000 }).includes("Vượt ngân sách"));
  assert.ok(!theBuoi({ kind: "chua-xong" }).includes("Vượt ngân sách"));
  assert.ok(!theBuoi({ kind: "khong-doc-duoc" }).includes("Vượt ngân sách"));
});

test("chuyến chưa xong không bịa ra 0đ đã tiêu trên thẻ", () => {
  const doc = theBuoi({ kind: "chua-xong" });
  assert.ok(!doc.includes("Đã tiêu"), `thẻ khẳng định một số tiền chưa hề đo: ${doc}`);
  assert.ok(doc.includes("Ngân sách 6.000.000đ"), doc);
  assert.ok(doc.includes("Chuyến chưa xong"), doc);
});

test("đọc sổ hỏng thì thẻ nói đúng cái đang thiếu", () => {
  const doc = theBuoi({ kind: "khong-doc-duoc" });
  assert.ok(!doc.includes("Đã tiêu"), doc);
  assert.ok(doc.includes("Chưa đọc được số đã tiêu"), doc);
  assert.ok(!doc.includes("Chuyến chưa xong"), `nói sai lý do: ${doc}`);
});

test("quy tắc gán khoản chi theo ngày của chuyến được nói ra trên thẻ", () => {
  // The server has no `expenses.outing_id`. Somebody comparing this against
  // their own memory deserves to know the rule before calling it a bug.
  const doc = theBuoi({ kind: "co", vnd: 4_500_000 });
  assert.ok(doc.includes("ngày của chuyến"), `quy tắc không được nói ra: ${doc}`);
});

test("không có dấu gạch dài trong câu chữ của khối ngân sách", () => {
  for (const nguon of [
    { kind: "co", vnd: 4_500_000 },
    { kind: "co", vnd: 7_200_000 },
    { kind: "chua-xong" },
    { kind: "khong-doc-duoc" },
  ]) {
    assert.ok(!theBuoi(nguon).includes("—"), `em-dash trên thẻ với nguồn ${nguon.kind}`);
  }
});
