/* Kỷ niệm in the RuDi shell (M6): the bridge module.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/rudi-ky-niem.test.mjs
 *
 * The wall pages by the server's cursor; a photo is uploaded then remembered
 * under an Attempt; a heart is one request and the counts are the server's;
 * a photo url that is not ours never gets our headers; achievements are
 * derived from the finance answer by App B's rules, never awarded here.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien } from "../dist-test/api.js";
import {
  cauCapDo,
  cauKyNiem,
  cauThongKeAlbum,
  cauThuocPhim,
  cauTuongTac,
  checkInKyNiem,
  demHuyHieuMo,
  docThanhTich,
  docTuongNhom,
  doiTim,
  guiBinhLuanCho,
  nguonAnh,
} from "../dist-test/rudi/ky-niem/ky-niem.js";

const AN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const WIRE = (id, extra = {}) => ({ id, context_id: "c-1", author_id: AN, kind: "photo", image_url: `/contexts/c-1/photos/${id}`, caption: null, place_id: null, place_name: null, lat: null, lng: null, created_at: "2026-09-04T01:00:00Z", cursor: `cur-${id}`, reaction_count: 2, comment_count: 1, viewer_has_reacted: false, ...extra });

test("docTuongNhom: một trang theo con trỏ máy chủ, đếm là số máy chủ, thiếu thì 0", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url) => {
    goi.push(String(url));
    return json(200, { context_id: "c-1", memories: [WIRE("m-1"), WIRE("m-2", { reaction_count: undefined, kind: "checkin", place_name: "Tiệm Nướng Xóm Lào", image_url: null })], next_cursor: "cur-m-2", has_more: true });
  };
  const trang = await docTuongNhom("c-1", AN, { before: "cur-m-0" });
  assert.match(goi[0], /\/contexts\/c-1\/memories\?limit=24&before=cur-m-0$/);
  assert.equal(trang.conNua, true);
  assert.equal(trang.conTro, "cur-m-2");
  assert.deepEqual(trang.kyNiem.map((k) => [k.id, k.reactionCount, k.toiDaTim]), [["m-1", 2, false], ["m-2", 0, false]]);
  assert.equal(cauKyNiem(trang.kyNiem[1]), "Check-in tại Tiệm Nướng Xóm Lào");
  assert.equal(cauKyNiem(trang.kyNiem[0]), "Ảnh của nhóm");
  assert.equal(cauTuongTac(trang.kyNiem[0]), "2 tim · 1 bình luận");
  datTokenPhien(null);
});

test("checkInKyNiem gửi place_id + caption dưới Idempotency-Key; doiTim là một request POST rồi DELETE", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    goi.push({ url: String(url), method: init.method, body: init.body ? JSON.parse(init.body) : null, key: init.headers?.["Idempotency-Key"] });
    if (String(url).endsWith("/checkins")) return json(201, WIRE("m-9", { kind: "checkin", place_name: "Quán Ốc Dì Bé", image_url: null, reaction_count: 0, comment_count: 0 }));
    if (init.method === "DELETE") return new Response(null, { status: 204 });
    return json(201, { id: "r-1", memory_id: "m-9", person_id: AN, created_at: "2026-09-04T01:00:00Z", reaction_count: 1 });
  };
  const attempt = { key: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", at: 1 };
  const k = await checkInKyNiem("c-1", "p-quan-oc-di-be", "  ngon  ", AN, attempt);
  assert.deepEqual(goi[0].body, { place_id: "p-quan-oc-di-be", caption: "ngon" });
  assert.equal(goi[0].key, attempt.key);
  assert.equal(k.kind, "checkin");
  const daTim = await doiTim(k, "c-1", AN);
  assert.equal(goi[1].method, "POST");
  assert.match(goi[1].url, /\/memories\/m-9\/reactions$/);
  assert.deepEqual([daTim.toiDaTim, daTim.reactionCount], [true, 1]);
  const boRoi = await doiTim(daTim, "c-1", AN);
  assert.equal(goi[2].method, "DELETE");
  assert.deepEqual([boRoi.toiDaTim, boRoi.reactionCount], [false, 0]);
  datTokenPhien(null);
});

test("guiBinhLuanCho cắt khoảng trắng và dùng Attempt riêng theo nội dung", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    goi.push({ body: JSON.parse(init.body), key: init.headers?.["Idempotency-Key"] });
    return json(201, { id: "bl-1", memory_id: "m-1", author_id: AN, display_name: "An QA", body: "đẹp quá", created_at: "2026-09-04T01:00:00Z" });
  };
  const attempts = {};
  const bl = await guiBinhLuanCho("c-1", "m-1", "  đẹp quá ", AN, attempts);
  assert.deepEqual(goi[0].body, { body: "đẹp quá" });
  assert.equal(Object.keys(attempts).length, 1);
  assert.deepEqual(bl, { id: "bl-1", tacGiaId: AN, tenTacGia: "An QA", noiDung: "đẹp quá", luc: "2026-09-04T01:00:00Z" });
  datTokenPhien(null);
});

test("nguonAnh: url máy chủ mang header của người gọi; url ngoài hoặc rỗng không được gửi kèm chứng thực", () => {
  datTokenPhien("token-thu");
  const n = nguonAnh("/contexts/c-1/photos/p-1", AN, "c-1");
  assert.match(n.uri, /\/contexts\/c-1\/photos\/p-1$/);
  assert.equal(n.headers.Authorization, "Bearer token-thu");
  assert.equal(nguonAnh("https://evil.example/x.png", AN, "c-1"), null);
  assert.equal(nguonAnh(null, AN, "c-1"), null);
  datTokenPhien(null);
});

test("album/reel copy: thống kê từ số máy chủ; thước phim nói ai dựng hoặc vì sao không", () => {
  const a = { outing_id: "o", title: "Keo QA", period_label: "4/9", starts_on: "2026-09-04", ends_on: "2026-09-04", in_progress: true, photo_count: 1, checkin_count: 1, place_count: 1, split_total_vnd: 200000, expense_count: 1, headcount: 2, cover: null };
  assert.equal(cauThongKeAlbum(a), "1\u00a0ảnh · 1\u00a0chỗ đã tới · 1\u00a0check-in · đã chia\u00a0200.000đ");
  assert.equal(cauThuocPhim({ context_id: "c", outing_id: "o", reeled: true, reason: "ok", source: "ai", title: "x", picks: [{}, {}, {}] }), "Rủ Đi AI dựng thước phim này, 3 cảnh.");
  assert.notEqual(cauThuocPhim({ context_id: "c", outing_id: "o", reeled: false, reason: "no_memories", source: "none", title: null, picks: [], considered_count: 0 }), "");
});

test("docThanhTich: cấp độ, huy hiệu, thử thách suy từ /people/{id}/finance theo luật App B", async () => {
  datTokenPhien("token-thu");
  globalThis.fetch = async () =>
    json(200, { person_id: AN, display_name: "An QA", spend_vnd: 200000, settled_vnd: 0, outstanding_vnd: 75000, receivable_vnd: 0, expense_count: 1, group_count: 1, movements: [] });
  const t = await docThanhTich(AN, Date.UTC(2026, 8, 4));
  assert.equal(t.so.expense_count, 1);
  assert.ok(t.tienDo.cap >= 1);
  assert.match(cauCapDo(t.tienDo), /^Cấp \d+ · \d+\/\d+ điểm tới cấp \d+$/);
  assert.match(demHuyHieuMo(t.huyHieu), /^\d+\/\d+ đã mở$/);
  assert.ok(Array.isArray(t.thuThach));
  assert.ok(Array.isArray(t.huyHieu) && t.huyHieu.length > 0);
  datTokenPhien(null);
});
