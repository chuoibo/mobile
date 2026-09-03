/* Which story a screen is telling, and why.
 *
 * The repo holds two apps: 54 screens wired to the real API, and 21 screens
 * that look like the product and read `fixtures.ts`. Every "the app is lying"
 * finding in the QA reports descends from that split. `nguon.ts` is the seam
 * where a RuDi screen asks which one it is.
 *
 * Two properties are pinned here, and they pull against each other:
 *
 *  - A signed-in person IS live. That is the whole point of adding
 *    `context_id` to `SessionResponse`; before it, somebody could hold a valid
 *    session and still be shown the demo.
 *  - Live is never REACHED BY ACCIDENT. No probe, no "the server answered so
 *    it must be real". Either a session says which group, or an operator typed
 *    a dev pair in. Anything else is the fixture, with the reason said out loud.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { nguonHienTai } from "../dist-test/rudi/nguon.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const CONTEXT = "1aa00000-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const PHIEN_ACTIVE = {
  person_id: ACTOR,
  context_id: CONTEXT,
  membership_state: "active",
};

test("chưa đăng nhập là bản trải nghiệm, và nói ra vì sao", () => {
  const nguon = nguonHienTai(null, {});
  assert.equal(nguon.kieu, "trai-nghiem");
  assert.match(nguon.viSao, /Chưa đăng nhập/);
});

test("đăng nhập rồi, và nhóm đã duyệt, thì đọc dữ liệu thật", () => {
  assert.deepEqual(nguonHienTai(PHIEN_ACTIVE, {}), {
    kieu: "live",
    actorId: ACTOR,
    contextId: CONTEXT,
  });
});

test("đã đăng nhập nhưng nhóm chưa duyệt thì KHÔNG live", () => {
  // Signing in is not joining. The server refuses this person's group data, so
  // rendering the group would show an empty trip where the truth is "nobody
  // has accepted you yet".
  for (const state of ["invited", "left"]) {
    const nguon = nguonHienTai({ ...PHIEN_ACTIVE, membership_state: state }, {});
    assert.equal(nguon.kieu, "trai-nghiem", state);
    assert.match(nguon.viSao, /duyệt/);
  }
});

test("phiên mang mã nhóm không đọc được thì không thành đường dẫn", () => {
  // `contextId` is interpolated into a request path. A malformed one is a run
  // of 404s that reads on screen as "máy chủ hỏng".
  for (const xau of ["", "team-da-lat", "../../etc", "  " + CONTEXT]) {
    const nguon = nguonHienTai({ ...PHIEN_ACTIVE, context_id: xau }, {});
    assert.equal(nguon.kieu, "trai-nghiem", xau);
  }
});

test("cặp dev vẫn là đường dev, và nó thắng khi có mặt", () => {
  // The native gate drives live screens without minting an invitation every
  // run. `tests/cau-hinh-ban-dung.test.mjs` refuses this pair in any shippable
  // build profile, which is what keeps it a dev door.
  assert.deepEqual(nguonHienTai(null, { actor: ACTOR, context: CONTEXT }), {
    kieu: "live",
    actorId: ACTOR,
    contextId: CONTEXT,
  });
});

test("nửa cấu hình dev là lỗi được nêu tên, không phải im lặng về fixture", () => {
  for (const moiTruong of [{ actor: ACTOR }, { context: CONTEXT }]) {
    const nguon = nguonHienTai(null, moiTruong);
    assert.equal(nguon.kieu, "trai-nghiem");
    assert.match(nguon.viSao, /Thiếu một nửa/);
  }
});

test("live không bao giờ tự tới", () => {
  // The property stated once: nothing but a session that names a group, or an
  // explicit dev pair, can produce a live source. No probing, ever.
  const khong = [
    [null, {}],
    [{ ...PHIEN_ACTIVE, membership_state: "invited" }, {}],
    [{ ...PHIEN_ACTIVE, context_id: "khong-phai-uuid" }, {}],
    [null, { actor: "khong-phai-uuid", context: "cung-khong" }],
    [null, { actor: ACTOR }],
  ];
  for (const [phien, moiTruong] of khong) {
    assert.equal(nguonHienTai(phien, moiTruong).kieu, "trai-nghiem", JSON.stringify(moiTruong));
  }
});
