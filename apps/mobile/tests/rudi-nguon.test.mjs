/* Which story a screen is telling, and why.
 *
 * The repo holds two apps: 54 screens wired to the real API, and 21 screens
 * that look like the product and read `fixtures.ts`. Every "the app is lying"
 * finding in the QA reports descends from that split. `nguon.ts` is the seam
 * where a RuDi screen asks which one it is, and these tests pin the property
 * that makes the answer trustworthy: it is DELIBERATE.
 *
 * The temptation the first test rules out is probing the server and going live
 * if something answers. That would make the numbers on somebody's screen depend
 * on whether a laptop was running, with no action of theirs -- the demo story
 * and a real group's money swapping places in silence.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { nguonHienTai } from "../dist-test/rudi/nguon.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const CONTEXT = "1aa00000-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

test("không cấu hình gì thì là bản trải nghiệm, dù có phiên hay không", () => {
  for (const coPhien of [false, true]) {
    const nguon = nguonHienTai(coPhien, {});
    assert.equal(nguon.kieu, "trai-nghiem", `coPhien=${coPhien}`);
    assert.equal(nguon.viSao.length > 0, true, "phải nói được vì sao");
  }
});

test("một phiên thôi CHƯA đủ, và lý do nói ra đúng chỗ thiếu", () => {
  // ADR-0014 shipped in #514, so a session is real. It still does not say WHICH
  // GROUP: `SessionResponse` carries no `context_id` and `contexts.py` declares
  // no route that lists a person's. Re-checked on origin/main at 03eb05a.
  const nguon = nguonHienTai(true, {});
  assert.equal(nguon.kieu, "trai-nghiem");
  assert.match(nguon.viSao, /route liệt kê nhóm/);
});

test("đủ cả hai nửa và đúng hình dạng thì mới live", () => {
  const nguon = nguonHienTai(false, { actor: ACTOR, context: CONTEXT });
  assert.deepEqual(nguon, { kieu: "live", actorId: ACTOR, contextId: CONTEXT });
});

test("nửa cấu hình là lỗi được nêu tên, không phải im lặng về fixture", () => {
  // Somebody who pinned a group and got the demo numbers would have no way to
  // tell that from the app working correctly.
  for (const moiTruong of [{ actor: ACTOR }, { context: CONTEXT }]) {
    const nguon = nguonHienTai(false, moiTruong);
    assert.equal(nguon.kieu, "trai-nghiem");
    assert.match(nguon.viSao, /Thiếu một nửa/);
  }
});

test("giá trị sai hình dạng bị chặn trước khi thành đường dẫn", () => {
  // These are interpolated into a request path. A malformed one is a run of
  // 404s that reads on screen as "máy chủ hỏng".
  const rac = ["", "team-da-lat", "../../etc", "46b55e67932b5415a5ee08fb2641a4ff", "  " + ACTOR];
  for (const xau of rac) {
    assert.equal(nguonHienTai(false, { actor: xau, context: CONTEXT }).kieu, "trai-nghiem", `actor=${xau}`);
    assert.equal(nguonHienTai(false, { actor: ACTOR, context: xau }).kieu, "trai-nghiem", `context=${xau}`);
  }
});

test("live không bao giờ tự tới: phải có người gõ cấu hình vào", () => {
  // The whole property, stated once. No argument other than an explicit
  // identity pair can produce a live source.
  const khong = [
    [false, {}],
    [true, {}],
    [true, { actor: ACTOR }],
    [false, { context: CONTEXT }],
    [true, { actor: "khong-phai-uuid", context: "cung-khong" }],
  ];
  for (const [coPhien, moiTruong] of khong) {
    assert.equal(nguonHienTai(coPhien, moiTruong).kieu, "trai-nghiem", JSON.stringify(moiTruong));
  }
});
