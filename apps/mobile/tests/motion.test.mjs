/**
 * Nhịp chuyển động của vỏ RuDi.
 *
 * Khối `motion` cũ trong tokens.json không ai đọc; hợp đồng hướng đi hứa
 * «motion <= 220ms» với những con số không code nào tra. Test này pin bốn bậc
 * (và trần của báo cáo 2026-09-05: state <= 240 ms, celebrate <= 650 ms), luật
 * Reduce Motion, luật tiền không animate trước domain state, và ngân sách
 * celebrate một lần mỗi sự kiện.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  EASING,
  MOTION_MS,
  celebrateOnce,
  durationFor,
  moneyCountUpMs,
} from "../dist-test/rudi/motion.js";

test("bốn bậc tăng dần và nằm trong trần đã chốt", () => {
  assert.deepEqual(MOTION_MS, { instant: 100, standard: 200, shared: 300, celebrate: 550 });
  assert.ok(MOTION_MS.instant < MOTION_MS.standard);
  assert.ok(MOTION_MS.standard < MOTION_MS.shared);
  assert.ok(MOTION_MS.shared < MOTION_MS.celebrate);
  assert.ok(MOTION_MS.standard <= 240, "state transition quá 240 ms là bắt người ta chờ");
  assert.ok(MOTION_MS.celebrate <= 650, "celebrate quá 650 ms là sân khấu");
});

test("Reduce Motion đưa mọi bậc trừ instant về 0", () => {
  assert.equal(durationFor("instant", true), 100);
  for (const step of ["standard", "shared", "celebrate"]) {
    assert.equal(durationFor(step, true), 0, `${step} phải về 0 khi giảm chuyển động`);
    assert.equal(durationFor(step, false), MOTION_MS[step]);
  }
});

test("tiền không đếm lên trước khi domain state hợp lệ", () => {
  assert.equal(moneyCountUpMs(false, false), 0);
  assert.equal(moneyCountUpMs(true, false), MOTION_MS.standard);
  assert.equal(moneyCountUpMs(true, true), 0);
});

test("celebrate là ngân sách một lần mỗi sự kiện, lần sau chỉ là standard", () => {
  const seen = new Set();
  assert.equal(celebrateOnce(seen, "keo:42:chot", false), MOTION_MS.celebrate);
  assert.equal(celebrateOnce(seen, "keo:42:chot", false), MOTION_MS.standard);
  assert.equal(celebrateOnce(seen, "bill:7:xong", false), MOTION_MS.celebrate);
  assert.equal(celebrateOnce(new Set(), "badge:1", true), 0, "giảm chuyển động thì không celebrate");
});

test("easing là cubic-bezier hợp lệ: bốn số, x trong [0,1]", () => {
  for (const [name, curve] of Object.entries(EASING)) {
    assert.equal(curve.length, 4, name);
    const [x1, , x2] = curve;
    assert.ok(x1 >= 0 && x1 <= 1 && x2 >= 0 && x2 <= 1, `${name}: x ngoài [0,1]`);
  }
});
