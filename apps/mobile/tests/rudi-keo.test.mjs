/* Kèo on the real API (M4): the wire helpers and the pure ones.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-keo.test.mjs
 *
 * What matters most: the timeline PUT now carries `place_id` (App B never
 * sent it, so a stop could not open a place); adding or attaching keeps the
 * other stops byte-for-byte; the server's refusal codes become sentences.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien, newAttempt } from "../dist-test/api.js";
import {
  cauDaToi,
  cauSoChang,
  changGuiTu,
  ganDiaDiem,
  gioTiepTheo,
  homNayIso,
  kiemTraChangMoi,
  luuLichTrinh,
  themChang,
} from "../dist-test/rudi/keo/keo.js";

const CHANG = [
  { id: "s-1", position: 0, at: "12:00", label: "Ăn trưa", place_name: null, place_id: null },
  { id: "s-2", position: 1, at: "18:00", label: "Ăn tối", place_name: "Xóm Lào", place_id: "p-tiem-nuong-xom-lao" },
];

test("themChang giữ nguyên chặng cũ (kể cả place_id) và xếp theo giờ", () => {
  const ra = themChang(CHANG, { at: "15:00", label: "Cafe", place_name: "Lưng Chừng", place_id: "p-lung-chung-cafe" });
  assert.deepEqual(
    ra.map((c) => [c.at, c.label, c.place_id]),
    [
      ["12:00", "Ăn trưa", null],
      ["15:00", "Cafe", "p-lung-chung-cafe"],
      ["18:00", "Ăn tối", "p-tiem-nuong-xom-lao"],
    ],
  );
});

test("ganDiaDiem đổi đúng một chặng, không đụng chặng khác", () => {
  const ra = ganDiaDiem(CHANG, "s-1", { id: "p-quan-oc-di-be", name: "Quán Ốc Dì Bé" });
  assert.deepEqual(ra[0], { at: "12:00", label: "Ăn trưa", place_name: "Quán Ốc Dì Bé", place_id: "p-quan-oc-di-be" });
  assert.deepEqual(ra[1], changGuiTu(CHANG[1]));
});

test("luuLichTrinh gửi place_id lên PUT /outings/{id}/timeline và dịch stop_place_unknown", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    goi.push({ url: String(url), body: JSON.parse(init.body) });
    if (goi.length === 1) {
      return new Response(JSON.stringify({ id: "o-1", context_id: "c-1", stops: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify({ code: "stop_place_unknown", detail: "x" }), { status: 422, headers: { "Content-Type": "application/json" } });
  };
  await luuLichTrinh({ id: "o-1", context_id: "c-1" }, changGuiTu(CHANG[1]) && [changGuiTu(CHANG[1])], "nguoi-1", newAttempt());
  assert.match(goi[0].url, /\/outings\/o-1\/timeline$/);
  assert.deepEqual(goi[0].body.stops[0], { at: "18:00", label: "Ăn tối", place_name: "Xóm Lào", place_id: "p-tiem-nuong-xom-lao" });
  await assert.rejects(
    luuLichTrinh({ id: "o-1", context_id: "c-1" }, [{ at: "18:00", label: "x", place_name: null, place_id: "p-la" }], "nguoi-1", newAttempt()),
    /không có trong danh mục/,
  );
  datTokenPhien(null);
});

test("câu đếm và câu đã tới nói đúng số", () => {
  assert.equal(cauSoChang(0), "Chưa có chặng nào");
  assert.equal(cauSoChang(2), "2 chặng");
  assert.equal(cauDaToi([], "toi"), "Chưa ai tới");
  const ci = (p) => ({ id: p, stop_id: "s", person_id: p, display_name: null, created_at: "2026-09-04T00:00:00Z" });
  assert.equal(cauDaToi([ci("ban")], "toi"), "1 đã tới");
  assert.equal(cauDaToi([ci("ban"), ci("toi")], "toi"), "2 đã tới · bạn");
});

test("mặc định ngày và giờ lấy từ đồng hồ máy, dạng máy chủ nhận", () => {
  assert.equal(homNayIso(new Date(2026, 8, 4, 23, 30)), "2026-09-04");
  assert.equal(gioTiepTheo(new Date(2026, 8, 4, 17, 5)), "18:00");
  assert.equal(gioTiepTheo(new Date(2026, 8, 4, 23, 5)), "00:00");
});

test("kiemTraChangMoi nói tại sao trước khi gọi máy chủ", () => {
  assert.deepEqual(kiemTraChangMoi("18:30", "Ăn tối"), { ok: true });
  assert.match(kiemTraChangMoi("6pm", "Ăn tối").loi, /24 giờ/);
  assert.match(kiemTraChangMoi("18:30", "   ").loi, /Đặt tên/);
  assert.match(kiemTraChangMoi("18:30", "x".repeat(201)).loi, /200/);
});
