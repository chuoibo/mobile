/* F14: nhận lời mời buổi đi. Token an toàn, khoá ghi, hai câu khác nhau.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/loi-moi-buoi-di.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import { nhanLoiMoiBuoiDi } from "../dist-test/api.js";
import { cauSauKhiNhan } from "../dist-test/rudi/loi-moi-den.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const LAN = { key: "a1b2c3d4-e5f6-4a1b-8c2d-e3f4a5b6c7d8", at: 0 };

test("invited và active cho ra hai câu khác nhau", () => {
  const vao = cauSauKhiNhan("active");
  const cho = cauSauKhiNhan("invited");
  assert.notEqual(vao, cho, "hai trạng thái không được gộp thành một câu thành công");
  assert.match(vao, /đã vào/);
  assert.match(cho, /duyệt|chờ/);
  assert.equal(vao.includes("thành công"), false);
  assert.equal(cho.includes("thành công"), false);
  assert.match(vao, /[ăâđêôơưàáảãạ]/i);
  assert.match(cho, /[ăâđêôơưàáảãạ]/i);
});