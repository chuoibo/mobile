/* The settlement hero's spending figure (M5): three states read from the recap.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-quyet-toan-tong.test.mjs
 *
 * The server's top-level `split_total_vnd` sums FINISHED trips, so a group whose
 * only trip is under way gets `0` -- printing that under "tổng chi tiêu" on the
 * day a bill was written is the defect flow 28's capture showed. Nothing here
 * adds money: the running figure is the server's own per-trip number.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { dongHeroQuyetToan, tongTuRecap } from "../dist-test/rudi/doc-live.js";

const CHUYEN = (title, tong) => ({ outing_id: "o-1", title, starts_on: "2026-09-04", ends_on: "2026-09-04", headcount: 2, stops: [], split_total_vnd: tong, expense_count: 1, memory_count: 0 });

test("chuyến đang đi: số đang chạy của chính chuyến đó, không phải tổng 0 của các chuyến đã xong", () => {
  const tong = tongTuRecap({ context_id: "c", outings: [], in_progress: [CHUYEN("Keo QA", 200000)], split_total_vnd: 0 });
  assert.deepEqual(tong, { kieu: "dang-di", ten: "Keo QA", tong: 200000, soChuyenDangDi: 1 });
  const hero = dongHeroQuyetToan(tong, 2);
  assert.equal(hero.nhan, "Đang đi: Keo QA (2 người)");
  assert.equal(hero.so, "200.000đ");
});

test("chỉ có chuyến đã kết thúc: tổng máy chủ và số chuyến", () => {
  const tong = tongTuRecap({ outings: [CHUYEN("A", 1000), CHUYEN("B", 2000)], in_progress: [], split_total_vnd: 3000 });
  assert.deepEqual(tong, { kieu: "da-ket-thuc", soChuyen: 2, tong: 3000 });
  assert.equal(dongHeroQuyetToan(tong, 3).nhan, "2 chuyến đã kết thúc (3 người)");
  assert.equal(dongHeroQuyetToan(tong, 3).so, "3.000đ");
});

test("không có chuyến nào: nói vậy, không in 0đ", () => {
  const tong = tongTuRecap({ outings: [], in_progress: [], split_total_vnd: 0 });
  assert.deepEqual(tong, { kieu: "chua-co-chuyen" });
  const hero = dongHeroQuyetToan(tong, 2);
  assert.equal(hero.so, "Chưa có chuyến");
  assert.doesNotMatch(hero.so + hero.nhan + hero.cau, /0đ/);
});

test("recap lệch hợp đồng (chuyến không tên, tiền không nguyên) → null, và null có câu riêng", () => {
  assert.equal(tongTuRecap({ outings: [], in_progress: [{ split_total_vnd: 1 }], split_total_vnd: 0 }), null);
  assert.equal(tongTuRecap({ outings: [CHUYEN("A", 1)], in_progress: [], split_total_vnd: 1.5 }), null);
  assert.equal(tongTuRecap(null), null);
  assert.equal(dongHeroQuyetToan(null, 2).so, "Chưa có số");
});
