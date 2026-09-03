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
  chonNhom,
  chonNhomMacDinh,
  dangXuat,
  docHoSoToi,
  docNhomCuaToi,
  doiLoiMoiLayPhien,
  ganDanhSachNhom,
  guiOtp,
  khoTrongBoNho,
  khoiPhucPhien,
  suaHoSoToi,
  vaoNhom,
  xacMinhOtp,
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

test("bản ghi không có nhóm là phiên hợp lệ CHƯA CÓ NHÓM, không bị đăng xuất (ADR-0016)", async () => {
  // This case used to assert the opposite: a record without `context_id` was
  // refused, because there was no route listing a person's groups and keeping
  // it would have signed somebody into a live-looking shell with nothing to
  // read. `GET /people/me/contexts` and the «Chưa có nhóm nào» screen exist
  // now, and the OTP door mints exactly this record for a new person -- so
  // refusing it would sign every new person out on their second launch.
  const kho = khoTrongBoNho();
  const { context_id: _bo, membership_state: _bo2, ...cu } = PHIEN;
  await kho.ghi("rudi.phien", JSON.stringify(cu));

  const phien = await khoiPhucPhien(kho);

  assert.ok(phien);
  assert.equal(phien.context_id, null);
  assert.equal(phien.membership_state, null);
  assert.equal(tokenPhienHienTai(), "tok-abc");
});

test("nhóm rỗng đọc thành null, không thành một nhóm tên là chuỗi rỗng", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify({ ...PHIEN, context_id: "" }));

  const phien = await khoiPhucPhien(kho);

  assert.equal(phien?.context_id, null);
});

test("phiên còn hạn mang theo nhóm của nó", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify(PHIEN));

  const phien = await khoiPhucPhien(kho);

  assert.equal(phien?.context_id, NHOM);
});

test("không có thẻ thành viên thì vaoNhom từ chối tại chỗ, không gửi PUT /memberships/null", async () => {
  // Same shift as above: the record is kept (`membership_id: null`), and the
  // thing that must not happen moves one step later -- the «Đồng ý» press. A
  // session with no membership card has nothing to accept, and saying so on
  // the phone beats a 404 from `/memberships/null` dressed as a server fault.
  const kho = khoTrongBoNho();
  const { membership_id: _bo, ...cu } = PHIEN;
  await kho.ghi("rudi.phien", JSON.stringify(cu));

  const phien = await khoiPhucPhien(kho);
  assert.ok(phien);
  assert.equal(phien.membership_id, null);

  const { impl, daGoi } = fetchGiaLap([]);
  await assert.rejects(voiFetch(impl, () => vaoNhom(phien, kho)), /không mang thẻ thành viên/);
  assert.equal(daGoi.length, 0, "đã gửi một request cho một thẻ không tồn tại");
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

/* ---- The OTP door (ADR-0016). --------------------------------------------
 *
 * Same discipline as `POST /sessions` above: the bodies are pinned key by key,
 * because the tempting extra field (`person_id`) is the one that hands the
 * client back the right to say who it is. And the number travels in ONE body
 * and nowhere else -- never a path, never a header, never a log line here.
 */
const NHOM_B = "3cc00000-cccc-4ccc-8ccc-cccccccccccc";
const THE_B = "4dd00000-dddd-4ddd-8ddd-dddddddddddd";
// Few digits on purpose: the repo guard reads nine digits in a row as a phone
// number, and it is right to.
const SO = "09 345 678";

const PHIEN_OTP = {
  token: "tok-otp",
  person_id: NGUOI,
  context_id: null,
  membership_state: null,
  membership_id: null,
  expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  issued_via: "otp",
  is_new_person: true,
  profile: { display_name: "Thành viên mới" },
  contexts: [],
};

const NHOM_MOI = {
  id: NHOM,
  display_name: "Được mời",
  my_state: "invited",
  membership_id: THE_THANH_VIEN,
  member_count: 2,
  unread_count: 0,
};
const NHOM_DANG_O = {
  id: NHOM_B,
  display_name: "Đang ở",
  my_state: "active",
  membership_id: THE_B,
  member_count: 3,
  unread_count: 1,
};

test("guiOtp: POST /auth/otp/request, thân chỉ có phone, không Bearer, không actor", async () => {
  const { impl, daGoi } = fetchGiaLap([
    traLoi({ challenge_id: "ch-1", expires_in_seconds: 300, resend_after_seconds: 60 }, { status: 202 }),
  ]);

  const ra = await voiFetch(impl, () => guiOtp(SO));

  assert.equal(daGoi.length, 1);
  assert.match(daGoi[0].url, /\/auth\/otp\/request$/);
  assert.equal(daGoi[0].init.method, "POST");
  assert.deepEqual(than(daGoi[0]), { phone: SO });
  assert.equal(daGoi[0].init.headers["Authorization"], undefined);
  assert.equal(daGoi[0].init.headers["X-Actor-ID"], undefined);
  assert.equal(ra.resend_after_seconds, 60);
});

test("guiOtp dịch mã từ chối của máy chủ thành câu người đọc", async () => {
  const { impl } = fetchGiaLap([
    traLoi({ code: "otp_resend_too_soon", detail: "x" }, { ok: false, status: 429 }),
  ]);

  await assert.rejects(
    voiFetch(impl, () => guiOtp(SO)),
    (loi) => loi.code === "otp_resend_too_soon" && loi.message === "Mã vừa được gửi. Đợi một chút rồi gửi lại.",
  );
});

test("xacMinhOtp: thân là {challenge_id, phone, code} có Idempotency-Key; phiên được ghi, Bearer được đặt", async () => {
  const kho = khoTrongBoNho();
  const { impl, daGoi } = fetchGiaLap([traLoi(PHIEN_OTP, { status: 201 }), traLoi({ ok: true })]);

  const phien = await voiFetch(impl, async () => {
    const ra = await xacMinhOtp("ch-1", SO, "000000", kho);
    await translatedAsActor({}, "/contexts/x", { method: "GET", actorId: NGUOI });
    return ra;
  });

  assert.match(daGoi[0].url, /\/auth\/otp\/verify$/);
  assert.deepEqual(than(daGoi[0]), { challenge_id: "ch-1", phone: SO, code: "000000" });
  assert.ok(daGoi[0].init.headers["Idempotency-Key"], "verify là một cú ghi: mất đáp án phải replay được");
  assert.equal(daGoi[1].init.headers["Authorization"], "Bearer tok-otp");
  // No group known: the session says so instead of inventing one.
  assert.equal(phien.context_id, null);
  assert.equal(phien.issued_via, "otp");
  const luu = JSON.parse(await kho.doc("rudi.phien"));
  assert.equal(luu.token, "tok-otp");
  assert.equal(luu.context_id, null);
});

test("xacMinhOtp chọn nhóm ACTIVE đầu tiên máy chủ liệt kê, bỏ qua nhóm chỉ mới được mời", async () => {
  const { impl } = fetchGiaLap([
    traLoi({ ...PHIEN_OTP, contexts: [NHOM_MOI, NHOM_DANG_O] }, { status: 201 }),
  ]);

  const phien = await voiFetch(impl, () => xacMinhOtp("ch-1", SO, "000000", khoTrongBoNho()));

  assert.equal(phien.context_id, NHOM_B);
  assert.equal(phien.membership_state, "active");
  assert.equal(phien.membership_id, THE_B);
});

test("chonNhomMacDinh để yên phiên đã có nhóm, và để yên phiên chỉ có lời mời", () => {
  assert.equal(chonNhomMacDinh(PHIEN).context_id, NHOM);
  const chiMoi = { ...PHIEN_OTP, contexts: [NHOM_MOI] };
  assert.equal(chonNhomMacDinh(chiMoi).context_id, null);
  assert.equal(chonNhomMacDinh(chiMoi).membership_id, null);
});

test("mã sai: câu của máy chủ (còn mấy lần) đi thẳng tới màn, không bị thay bằng chữ cứng", async () => {
  const { impl } = fetchGiaLap([
    traLoi({ code: "otp_code_invalid", detail: "Mã chưa đúng. Còn 4 lần thử." }, { ok: false, status: 422 }),
  ]);

  await assert.rejects(
    voiFetch(impl, () => xacMinhOtp("ch-1", SO, "111111", khoTrongBoNho())),
    (loi) => loi.code === "otp_code_invalid" && loi.message === "Mã chưa đúng. Còn 4 lần thử.",
  );
  // And nothing was remembered from a refused code.
  assert.equal(tokenPhienHienTai(), null);
});

test("khoiPhucPhien đọc được phiên OTP không có nhóm thay vì coi bản ghi là hỏng", async () => {
  const kho = khoTrongBoNho();
  await kho.ghi("rudi.phien", JSON.stringify(PHIEN_OTP));

  const phien = await khoiPhucPhien(kho);

  assert.ok(phien, "phiên hợp lệ bị đọc thành null: người đã đăng nhập bị đăng xuất mỗi lần mở app");
  assert.equal(phien.context_id, null);
  assert.equal(phien.membership_state, null);
  assert.equal(phien.membership_id, null);
  assert.equal(phien.issued_via, "otp");
  assert.equal(tokenPhienHienTai(), "tok-otp");
});

test("docNhomCuaToi: GET /people/me/contexts mang Bearer của phiên", async () => {
  const kho = khoTrongBoNho();
  const { impl, daGoi } = fetchGiaLap([
    traLoi(PHIEN_OTP, { status: 201 }),
    traLoi({ contexts: [NHOM_DANG_O] }),
  ]);

  const ds = await voiFetch(impl, async () => {
    await xacMinhOtp("ch-1", SO, "000000", kho);
    return docNhomCuaToi(NGUOI);
  });

  assert.match(daGoi[1].url, /\/people\/me\/contexts$/);
  assert.equal(daGoi[1].init.method, "GET");
  assert.equal(daGoi[1].init.headers["Authorization"], "Bearer tok-otp");
  assert.equal(ds.length, 1);
  assert.equal(ds[0].id, NHOM_B);
});

test("ganDanhSachNhom gán nhóm active vào phiên và ghi lại kho", async () => {
  const kho = khoTrongBoNho();

  const moi = await ganDanhSachNhom(PHIEN_OTP, [NHOM_DANG_O], kho);

  assert.equal(moi.context_id, NHOM_B);
  assert.equal(moi.membership_state, "active");
  assert.equal(JSON.parse(await kho.doc("rudi.phien")).context_id, NHOM_B);
});

/* ---- M2: picking a group, and the profile routes. ------------------------ */

test("chonNhom chỉ nhận nhóm máy chủ đã liệt kê và đã active, rồi ghi lại kho", async () => {
  const kho = khoTrongBoNho();
  const phien = { ...PHIEN_OTP, contexts: [NHOM_MOI, NHOM_DANG_O] };

  const moi = await chonNhom(phien, NHOM_B, kho);
  assert.equal(moi.context_id, NHOM_B);
  assert.equal(moi.membership_id, THE_B);
  assert.equal(JSON.parse(await kho.doc("rudi.phien")).context_id, NHOM_B);

  await assert.rejects(chonNhom(phien, NHOM, kho), /chưa đồng ý/);
  await assert.rejects(chonNhom(phien, "5ee00000-eeee-4eee-8eee-eeeeeeeeeeee", kho), /không có trong danh sách/);
});

test("docHoSoToi: GET /people/me mang Bearer; suaHoSoToi: PATCH chỉ gửi trường được đổi, có Idempotency-Key", async () => {
  const kho = khoTrongBoNho();
  const hoSo = {
    id: NGUOI,
    display_name: "Tôi",
    bio: null,
    city: null,
    created_at: PHIEN_OTP.expires_at,
    counts: { friends: 1, contexts: 1, outings: 0, places_checked_in: 0, memories: 0 },
    login_methods: ["phone"],
  };
  const { impl, daGoi } = fetchGiaLap([
    traLoi(PHIEN_OTP, { status: 201 }),
    traLoi(hoSo),
    traLoi({ ...hoSo, bio: "Cafe sáng" }),
  ]);

  const ket = await voiFetch(impl, async () => {
    await xacMinhOtp("ch-1", SO, "000000", kho);
    const doc = await docHoSoToi(NGUOI);
    const sua = await suaHoSoToi(NGUOI, { bio: "Cafe sáng" });
    return { doc, sua };
  });

  assert.match(daGoi[1].url, /\/people\/me$/);
  assert.equal(daGoi[1].init.method, "GET");
  assert.equal(daGoi[1].init.headers["Authorization"], "Bearer tok-otp");
  assert.equal(ket.doc.counts.friends, 1);
  assert.match(daGoi[2].url, /\/people\/me$/);
  assert.equal(daGoi[2].init.method, "PATCH");
  assert.deepEqual(than(daGoi[2]), { bio: "Cafe sáng" });
  assert.ok(daGoi[2].init.headers["Idempotency-Key"]);
  assert.equal(ket.sua.bio, "Cafe sáng");
});
