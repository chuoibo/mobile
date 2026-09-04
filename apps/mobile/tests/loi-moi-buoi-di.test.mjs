/* F14: nhận lời mời buổi đi. Token an toàn, khoá ghi, hai câu khác nhau.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/loi-moi-buoi-di.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import { nhanLoiMoiBuoiDi } from "../dist-test/api.js";
import { docDiemDen } from "../dist-test/navigation/lien-ket.js";
import { cauSauKhiNhan } from "../dist-test/rudi/loi-moi-den.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const LAN = { key: "a1b2c3d4-e5f6-4a1b-8c2d-e3f4a5b6c7d8", at: 0 };

function res(body, { status = 200 } = {}) {
  const ok = status >= 200 && status < 300;
  return {
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

async function withFetch(impl, fn) {
  const previous = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = previous;
  }
}

test("docDiemDen đọc được #moi=abc", () => {
  const d = docDiemDen("#moi=abc");
  assert.equal(d.moiBuoiDi, "abc");
  assert.equal(d.boQuaMoDau, true);
});

test("token có / hoặc .. bị từ chối thành null", () => {
  for (const hash of ["#moi=a/b", "#moi=foo/bar", "#moi=..", "#moi=foo..bar", "#moi=../x"]) {
    const d = docDiemDen(hash);
    assert.equal(d.moiBuoiDi, null, `${hash} phải bị từ chối`);
    assert.equal(d.boQuaMoDau, false, `${hash} không được bỏ qua màn mở đầu`);
  }
});

test("token rỗng là null, không phải chuỗi rỗng", () => {
  for (const hash of ["#moi=", "#moi=%20%20", ""]) {
    assert.equal(docDiemDen(hash).moiBuoiDi, null, hash);
  }
});

test("accept gửi Idempotency-Key và đúng đường", async () => {
  const goi = [];
  await withFetch(async (url, init) => {
    goi.push({ url: String(url), method: init?.method, headers: init?.headers });
    return res({
      invite_id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      outing_id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
      context_id: "cccccccc-dddd-4eee-8fff-aaaaaaaaaaaa",
      membership_id: "dddddddd-eeee-4fff-8aaa-bbbbbbbbbbbb",
      membership_state: "active",
    });
  }, () => nhanLoiMoiBuoiDi("token-thu", ACTOR, LAN));

  assert.equal(goi.length, 1);
  assert.equal(goi[0].method, "POST");
  assert.equal(new URL(goi[0].url).pathname, "/outing-invites/token-thu/accept");
  assert.equal(goi[0].headers["Idempotency-Key"], LAN.key);
  assert.equal(goi[0].headers["X-Actor-ID"], ACTOR);
});

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
