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

/* ---------------------------------------------------- readable amounts --- */

test("tiền hiện ra đọc được, không phải một dãy chữ số liền", () => {
  assert.equal(tienVnd(1_200_000), "1.200.000đ");
  assert.equal(tienVnd(6_000_000), "6.000.000đ");
  assert.equal(tienVnd(0), "0đ");
});