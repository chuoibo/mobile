/* The chat wire and its pure helpers (M3).
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-chat-tin-song.test.mjs
 *
 * What matters most: an inverted list wants newest-first and a forward poll
 * answers oldest-first -- `gopTin` must make one order out of both, with no
 * duplicates. Day dividers sit under (list order) the messages of their day.
 * Cards of an unexpected shape become «khac», never a crash.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien } from "../dist-test/api.js";
import {
  cauYDinh,
  cursorCuNhat,
  cursorMoiNhat,
  docTheAi,
  docTrangTin,
  glyphPhanUng,
  gopTin,
  guiTin,
  nhanNgay,
  nhomTheoNgay,
  thayPhanUng,
  themPhanUng,
} from "../dist-test/rudi/chat/tin-song.js";

const CTX = "3cc00000-cccc-4ccc-8ccc-0000c0000009";
const ME = "4dd00000-dddd-4ddd-8ddd-0000d0000009";

function tin(id, at, extra = {}) {
  return {
    id,
    context_id: CTX,
    author_id: ME,
    kind: "text",
    body: id,
    image_url: null,
    card: null,
    created_at: at,
    cursor: `c-${id}`,
    ...extra,
  };
}

test.afterEach(() => datTokenPhien(null));

test("gopTin trả newest-first, không trùng, từ hai đầu vào thứ tự khác nhau", () => {
  const dangGiu = [tin("b", "2030-08-27T12:01:00Z"), tin("a", "2030-08-27T12:00:00Z")];
  const trangSau = [tin("b", "2030-08-27T12:01:00Z"), tin("c", "2030-08-27T12:02:00Z")]; // ascending
  const ra = gopTin(dangGiu, trangSau);
  assert.deepEqual(ra.map((t) => t.id), ["c", "b", "a"]);
  assert.equal(cursorMoiNhat(ra), "c-c");
  assert.equal(cursorCuNhat(ra), "c-a");
  assert.equal(cursorMoiNhat([]), null);
});

test("nhomTheoNgay đặt vạch ngày dưới (theo thứ tự list) các tin của ngày đó", () => {
  const homNay = new Date("2030-08-27T20:00:00Z");
  const ra = nhomTheoNgay(
    [tin("b", "2030-08-27T12:01:00Z"), tin("a", "2030-08-26T09:00:00Z")],
    homNay,
  );
  assert.deepEqual(
    ra.map((h) => (h.loai === "tin" ? h.tin.id : h.nhan)),
    ["b", "Hôm nay", "a", "Hôm qua"],
  );
  assert.equal(nhanNgay("2030-08-20", homNay), "20/08");
});

test("docTheAi đọc năm loại thẻ và trả «khac» cho hình dạng lạ", () => {
  assert.deepEqual(docTheAi({ kind: "text", payload: { text: "Đi thôi" } }), { loai: "text", text: "Đi thôi" });
  const poll = docTheAi({
    kind: "poll",
    payload: { vote_id: "v1", question: "Ăn gì?", options: [{ id: "o1", label: "Bún" }, { id: "o2", label: "Phở" }] },
  });
  assert.equal(poll.loai, "poll");
  assert.equal(poll.options.length, 2);
  assert.equal(docTheAi({ kind: "poll", payload: { vote_id: "v1", question: "?", options: [{ id: "o1", label: "x" }] } }).loai, "khac", "một lựa chọn không phải bình chọn");
  const nhap = docTheAi({
    kind: "expense_draft",
    payload: { drafts: [{ title: "Ăn", amount_vnd: 180000, paid_by_id: ME, shared_by: [ME], needs_review: true }] },
  });
  assert.equal(nhap.loai, "expense_draft");
  assert.equal(nhap.drafts[0].amount_vnd, 180000);
  assert.equal(docTheAi(null).loai, "khac");
  assert.equal(docTheAi({ kind: "poll_vote", payload: {} }).loai, "khac");
  assert.equal(docTheAi("x").loai, "khac");
});

test("thayPhanUng chỉ đụng đúng một tin; glyph có cho cả sáu loại", () => {
  const ra = thayPhanUng([tin("a", "2030-08-27T12:00:00Z"), tin("b", "2030-08-27T12:01:00Z")], "a", [
    { kind: "heart", count: 2, mine: true },
  ]);
  assert.deepEqual(ra[0].reactions, [{ kind: "heart", count: 2, mine: true }]);
  assert.equal(ra[1].reactions, undefined);
  for (const k of ["heart", "haha", "like", "wow", "sad", "fire"]) assert.notEqual(glyphPhanUng(k), "•");
  assert.equal(glyphPhanUng("poop"), "•");
});

test("cauYDinh nói đúng điều máy chủ làm với lệnh", () => {
  assert.match(cauYDinh({ ...tin("a", "2030-08-27T12:00:00Z"), intent_error: "companion_rate_limited" }), /Hết lượt/);
  assert.match(cauYDinh({ ...tin("a", "2030-08-27T12:00:00Z"), intent_error: "vote_malformed" }), /\/vote/);
  assert.match(
    cauYDinh({ ...tin("a", "2030-08-27T12:00:00Z"), companion: { context_id: CTX, spoke: false, reason: "unavailable", message: null } }),
    /chưa nối được mô hình/,
  );
  assert.equal(cauYDinh({ ...tin("a", "2030-08-27T12:00:00Z"), companion: { context_id: CTX, spoke: true, reason: "ok", message: tin("z", "2030-08-27T12:00:01Z") } }), null);
  assert.equal(cauYDinh(tin("a", "2030-08-27T12:00:00Z")), null);
});

function traLoi(body, status = 200) {
  return { ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) };
}

test("docTrangTin/guiTin/themPhanUng đi đúng route với Bearer, Idempotency-Key cho cú ghi", async () => {
  datTokenPhien("tok-chat");
  const daGoi = [];
  const truoc = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    daGoi.push({ url, init });
    if (url.includes("/reactions")) return traLoi({ message_id: "a", reactions: [{ kind: "heart", count: 1, mine: true }] }, 201);
    if (init.method === "POST") return traLoi({ ...tin("m", "2030-08-27T12:00:00Z"), intent: null }, 201);
    return traLoi({ context_id: CTX, messages: [], next_cursor: "c-x", has_more: false });
  };
  try {
    const trang = await docTrangTin(CTX, ME, { after: "c-x" });
    assert.equal(trang.next_cursor, "c-x", "trang rỗng echo cursor");
    assert.match(daGoi[0].url, /\/contexts\/[^/]+\/messages\?limit=50&after=c-x$/);
    assert.equal(daGoi[0].init.headers["Authorization"], "Bearer tok-chat");
    await guiTin(CTX, ME, "xin chào", { key: "k1", at: 1 });
    assert.equal(daGoi[1].init.method, "POST");
    assert.deepEqual(JSON.parse(daGoi[1].init.body), { kind: "text", body: "xin chào", image_url: null, card: null });
    assert.equal(daGoi[1].init.headers["Idempotency-Key"], "k1");
    await themPhanUng(CTX, "a", ME, "heart");
    assert.match(daGoi[2].url, /\/messages\/a\/reactions$/);
    assert.deepEqual(JSON.parse(daGoi[2].init.body), { kind: "heart" });
    assert.ok(daGoi[2].init.headers["Idempotency-Key"]);
  } finally {
    globalThis.fetch = truoc;
  }
});
