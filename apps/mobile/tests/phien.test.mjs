/* The client half of ADR-0014: what goes on the wire when somebody signs in.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/phien.test.mjs
 *
 * The case that matters most is the shortest one: `POST /sessions` must carry
 * the invitation secret and NOTHING ELSE. A `person_id` in that body would put
 * the client back in charge of saying who it is, which is the hole the whole
 * change exists to close -- and it would be an easy, well-meaning line to add,
 * because every other request in this app names its actor.
 *
 * The rest is the plumbing that makes a session useful: the token reaches the
 * `Authorization` header of ordinary calls, an expired stored record is
 * dropped instead of sent, and signing out tells the server rather than only
 * the phone.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien, tokenPhienHienTai, translatedAsActor } from "../dist-test/api.js";
import {
  dangXuat,
  doiLoiMoiLayPhien,
  khoTrongBoNho,
  khoiPhucPhien,
  vaoNhom,
} from "../dist-test/phien.js";

const NGUOI = "2bb00000-bbbb-4bbb-8bbb-0000b0000001";

function traLoi(body, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

/** Record every request, and answer each one from a queue. */
function fetchGiaLap(dapAn) {
  const daGoi = [];
  const impl = async (url, init) => {
    daGoi.push({ url, init });
    const tiep = dapAn.shift();
    if (tiep === undefined) throw new Error(`không có đáp án cho ${url}`);
    return tiep;
  };
  return { impl, daGoi };
}

async function voiFetch(impl, fn) {
  const truoc = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = truoc;
  }
}

function than(goi) {
  return JSON.parse(goi.init.body);
}

const NHOM = "1aa00000-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const THE_THANH_VIEN = "2bb00000-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const PHIEN = {
  token: "tok-abc",
  person_id: NGUOI,
  context_id: NHOM,
  expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  membership_state: "invited",
  membership_id: THE_THANH_VIEN,
};

test.afterEach(() => {
  datTokenPhien(null);
});

test("thân của POST /sessions chỉ có mã lời mời, KHÔNG có person_id", async () => {
  const { impl, daGoi } = fetchGiaLap([traLoi(PHIEN, { status: 201 })]);

  await voiFetch(impl, () => doiLoiMoiLayPhien("moi-xyz", khoTrongBoNho()));

  assert.equal(daGoi.length, 1);
  assert.match(daGoi[0].url, /\/sessions$/);
  assert.equal(daGoi[0].init.method, "POST");
  const body = than(daGoi[0]);
  assert.deepEqual(Object.keys(body), ["invite_token"]);
  assert.equal(body.invite_token, "moi-xyz");
  // Said twice on purpose: the key list above is what breaks if somebody adds
  // a field, and this is what explains why that break is correct.
  assert.equal(body.person_id, undefined);
});

test("POST /sessions gửi Idempotency-Key, vì mất đáp án là mất luôn lời mời", async () => {
  const { impl, daGoi } = fetchGiaLap([traLoi(PHIEN, { status: 201 })]);

  await voiFetch(impl, () => doiLoiMoiLayPhien("moi-xyz", khoTrongBoNho()));

  const key = daGoi[0].init.headers["Idempotency-Key"];
  assert.ok(key, "thiếu Idempotency-Key: đáp án rơi là bị khoá ngoài ứng dụng");
});

test("đăng nhập xong thì mọi lời gọi có actor đều mang Bearer", async () => {
  const kho = khoTrongBoNho();
  const { impl, daGoi } = fetchGiaLap([
    traLoi(PHIEN, { status: 201 }),
    traLoi({ ok: true }),
  ]);

  await voiFetch(impl, async () => {
    await doiLoiMoiLayPhien("moi-xyz", kho);
    await translatedAsActor({}, "/contexts/x", { method: "GET", actorId: NGUOI });
  });

  assert.equal(daGoi[1].init.headers["Authorization"], "Bearer tok-abc");
  // The header adapter is still sent: one build has to work against a `dev`
  // demo box and against a `prod` host without a flag.
  assert.equal(daGoi[1].init.headers["X-Actor-ID"], NGUOI);
});

test("chưa đăng nhập thì không có Authorization nào được bịa ra", async () => {
  const { impl, daGoi } = fetchGiaLap([traLoi({ ok: true })]);

  await voiFetch(impl, () =>
    translatedAsActor({}, "/contexts/x", { method: "GET", actorId: NGUOI }),
  );

  assert.equal(daGoi[0].init.headers["Authorization"], undefined);
});

test("khoiPhucPhien đặt lại token từ kho", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify(PHIEN));

  const phien = await khoiPhucPhien(kho);

  assert.equal(phien?.person_id, NGUOI);
  assert.equal(tokenPhienHienTai(), "tok-abc");
});

test("phiên đã hết hạn bị bỏ tại chỗ, không gửi lên để nhận 401", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi(
    "rudi.phien",
    JSON.stringify({ ...PHIEN, expires_at: new Date(Date.now() - 1000).toISOString() }),
  );

  const phien = await khoiPhucPhien(kho);

  assert.equal(phien, null);
  assert.equal(tokenPhienHienTai(), null);
  assert.equal(await kho.doc("rudi.phien"), null, "bản ghi chết phải bị xoá");
});

test("bản ghi cũ không có nhóm thì bị từ chối, không phải đăng nhập nửa vời", async () => {
  // A record written before the server answered with `context_id`. Keeping it
  // would sign somebody in with nothing to read: there is no route that lists
  // a person's contexts, so the app would show a live-looking shell with no
  // group behind it. Refusing signs them out, and signing back in is one tap.
  const kho = khoTrongBoNho();
  const { context_id: _bo, ...cu } = PHIEN;
  await kho.ghi("rudi.phien", JSON.stringify(cu));

  assert.equal(await khoiPhucPhien(kho), null);
  assert.equal(tokenPhienHienTai(), null);
});

test("nhóm rỗng cũng là bản ghi không dùng được", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify({ ...PHIEN, context_id: "" }));

  assert.equal(await khoiPhucPhien(kho), null);
});

test("phiên còn hạn mang theo nhóm của nó", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify(PHIEN));

  const phien = await khoiPhucPhien(kho);

  assert.equal(phien?.context_id, NHOM);
});

test("bản ghi cũ không có thẻ thành viên cũng bị từ chối", async () => {
  // Cùng lý do với `context_id` ngay trên. Một bản ghi viết trước khi máy chủ
  // trả `membership_id` không đưa người `invited` đi đâu được: nút «Đồng ý vào
  // nhóm» cần đúng cái id đó, và route duy nhất liệt kê thẻ thành viên lại nằm
  // SAU chính cái thẻ đang chờ đồng ý. Giữ bản ghi ấy là để người ta ngồi mãi
  // ở màn có một nút không bao giờ chạy được.
  const kho = khoTrongBoNho();
  const { membership_id: _bo, ...cu } = PHIEN;
  await kho.ghi("rudi.phien", JSON.stringify(cu));

  assert.equal(await khoiPhucPhien(kho), null);
  assert.equal(tokenPhienHienTai(), null);
});

test("vào nhóm ghi lại TRẠNG THÁI CỦA MÁY CHỦ, không tự đặt là active", async () => {
  // Ca này đo phần dễ viết sai nhất: sau khi bấm đồng ý, cái được lưu phải là
  // câu trả lời của máy chủ. Vá tại chỗ thành "active" cũng qua được một ca
  // chỉ nhìn đường hạnh phúc — nên máy chủ ở đây cố tình trả `invited`, và bản
  // ghi trên đĩa phải nói đúng như vậy.
  const kho = khoTrongBoNho();
  const { impl, daGoi } = fetchGiaLap([traLoi({ state: "invited" }, { status: 200 })]);
  datTokenPhien(PHIEN.token);

  const sau = await voiFetch(impl, () => vaoNhom(PHIEN, kho));

  assert.equal(daGoi.length, 1);
  assert.equal(daGoi[0].init.method, "POST");
  assert.match(daGoi[0].url, new RegExp(`/memberships/${THE_THANH_VIEN}/accept$`));
  assert.equal(sau.membership_state, "invited");
  assert.equal(JSON.parse(await kho.doc("rudi.phien")).membership_state, "invited");
});

test("vào nhóm được thì cả bộ nhớ lẫn đĩa đều nói active", async () => {
  const kho = khoTrongBoNho();
  const { impl } = fetchGiaLap([traLoi({ state: "active" }, { status: 200 })]);
  datTokenPhien(PHIEN.token);

  const sau = await voiFetch(impl, () => vaoNhom(PHIEN, kho));

  assert.equal(sau.membership_state, "active");
  const tren_dia = JSON.parse(await kho.doc("rudi.phien"));
  assert.equal(tren_dia.membership_state, "active");
  // Phần còn lại của phiên phải đi qua nguyên vẹn: đổi một trường không được
  // làm rơi ba trường kia.
  assert.equal(tren_dia.membership_id, THE_THANH_VIEN);
  assert.equal(tren_dia.context_id, NHOM);
  assert.equal(tren_dia.token, PHIEN.token);
});

test("bản ghi hỏng là ứng dụng chưa đăng nhập, không phải ứng dụng vỡ", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", "{ không phải json");

  assert.equal(await khoiPhucPhien(kho), null);
});

test("đăng xuất gọi máy chủ trước rồi mới quên trên máy", async () => {
  const kho = khoTrongBoNho();
  const { impl, daGoi } = fetchGiaLap([
    traLoi(PHIEN, { status: 201 }),
    traLoi(null, { status: 204 }),
  ]);

  await voiFetch(impl, async () => {
    await doiLoiMoiLayPhien("moi-xyz", kho);
    await dangXuat(NGUOI, kho);
  });

  assert.match(daGoi[1].url, /\/sessions\/current$/);
  assert.equal(daGoi[1].init.method, "DELETE");
  // The server has to be told with the credential being revoked, or it revokes
  // nothing.
  assert.equal(daGoi[1].init.headers["Authorization"], "Bearer tok-abc");
  assert.equal(tokenPhienHienTai(), null);
  assert.equal(await kho.doc("rudi.phien"), null);
});

test("máy chủ từ chối đăng xuất thì máy vẫn quên phiên", async () => {
  const kho = khoTrongBoNho();
  const { impl } = fetchGiaLap([
    traLoi(PHIEN, { status: 201 }),
    traLoi({ code: "authentication_required" }, { ok: false, status: 401 }),
  ]);

  await voiFetch(impl, async () => {
    await doiLoiMoiLayPhien("moi-xyz", kho);
    await assert.rejects(() => dangXuat(NGUOI, kho));
  });

  // Người đã bấm đăng xuất thì phải được đăng xuất trên máy này, dù máy chủ
  // trả lời thế nào. Hàng trên máy chủ vẫn hết hạn theo TTL của nó.
  assert.equal(tokenPhienHienTai(), null);
  assert.equal(await kho.doc("rudi.phien"), null);
});
