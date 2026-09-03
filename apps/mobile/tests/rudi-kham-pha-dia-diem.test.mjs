/* Khám phá on the real catalogue (M4): the wire and the pure helpers.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-kham-pha-dia-diem.test.mjs
 *
 * What matters most: the catalogue is read as nobody with NO synthetic
 * context_id on the query string; saving goes with the bearer; the parsers
 * are App B's, so a fractional đồng or an invented match never reaches a
 * card; the sentences for a search that did not answer are honest ones.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien } from "../dist-test/api.js";
import {
  bieuTuongLoai,
  boLuuDiaDiem,
  cauMoCua,
  cauTimKiem,
  daoLuu,
  docChiTiet,
  docDaLuu,
  docDanhMuc,
  dongPhu,
  duongChiDuong,
  locTheoTen,
  luuDiaDiem,
} from "../dist-test/rudi/kham-pha/dia-diem.js";

const CHO = {
  id: "p-1",
  name: "Tiệm Nướng Xóm Lào",
  category: "quan-an-local",
  kinds: ["BBQ", "Lào"],
  rating: 4.7,
  rating_count: 128,
  distance_km: 1.2,
  price_min_vnd: 200000,
  price_max_vnd: 250000,
  address: "27/1 Yersin",
  open_now: true,
  open_hours: "10:00 - 22:30",
  travel_minutes: 25,
  photo_count: 18,
  traits: ["Chill", "Nhóm đông"],
  group_fit: { min_people: 4, max_people: 12, relation: "Bạn bè" },
  flag: null,
  lat: 11.94,
  lng: 108.44,
  match: null,
};

function gia(handler) {
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    goi.push({ url: String(url), init });
    const ra = handler(String(url), init);
    // A 204 has no body by definition; Response() throws if given one.
    if (ra.status === 204) return new Response(null, { status: 204 });
    return new Response(JSON.stringify(ra.body), { status: ra.status, headers: { "Content-Type": "application/json" } });
  };
  return goi;
}

test("docDanhMuc đọc /places như người lạ, không mang context_id bịa, lọc theo category và q", async () => {
  const goi = gia(() => ({ status: 200, body: { places: [CHO], categories: [{ id: "cafe", label: "Cafe" }], group: {} } }));
  const dm = await docDanhMuc({ category: "cafe", q: "  nướng " });
  assert.equal(dm.places[0].name, "Tiệm Nướng Xóm Lào");
  assert.equal(dm.places[0].priceMinVnd, 200000);
  assert.deepEqual(dm.categories, [{ id: "cafe", label: "Cafe" }]);
  assert.match(goi[0].url, /\/places\?category=cafe&q=n/);
  assert.doesNotMatch(goi[0].url, /context_id/);
  assert.equal((goi[0].init.method ?? "GET").toUpperCase(), "GET");
  assert.equal(goi[0].init.headers?.Authorization, undefined, "danh mục là công khai");
});

test("docDanhMuc từ chối đồng lẻ như App B từng làm", async () => {
  gia(() => ({ status: 200, body: { places: [{ ...CHO, price_min_vnd: 199.5 }], categories: [] } }));
  await assert.rejects(docDanhMuc());
});

test("docChiTiet mã hoá id và đọc chi tiết; 404 thành câu của danh mục", async () => {
  const goi = gia((url) =>
    url.includes("p-1")
      ? { status: 200, body: { ...CHO, description: "Ngon", reviews: [], photos_available: false } }
      : { status: 404, body: { code: "place_not_found", detail: "x" } },
  );
  const ct = await docChiTiet("p-1");
  assert.equal(ct.description, "Ngon");
  assert.match(goi[0].url, /\/places\/p-1$/);
  await assert.rejects(docChiTiet("p-la"), /không còn trong danh mục/);
});

test("lưu / bỏ lưu đi với bearer; danh sách đã lưu chỉ lấy place_id chuỗi", async () => {
  datTokenPhien("token-thu");
  const goi = gia((url, init) => {
    if ((init.method ?? "GET") === "GET") return { status: 200, body: { saved: [{ place_id: "p-1" }, { place_id: 7 }, {}] } };
    return { status: init.method === "PUT" ? 201 : 204, body: {} };
  });
  assert.deepEqual(await docDaLuu("nguoi-1"), ["p-1"]);
  await luuDiaDiem("nguoi-1", "p-2");
  await boLuuDiaDiem("nguoi-1", "p-2");
  assert.equal(goi[1].init.method, "PUT");
  assert.match(goi[1].url, /\/people\/me\/saved-places\/p-2$/);
  assert.equal(goi[2].init.method, "DELETE");
  for (const g of goi) assert.match(g.init.headers.Authorization, /^Bearer /);
  datTokenPhien(null);
});

test("daoLuu thêm hoặc bỏ đúng một id, không đụng phần còn lại", () => {
  assert.deepEqual(daoLuu(["a"], "b"), ["a", "b"]);
  assert.deepEqual(daoLuu(["a", "b"], "a"), ["b"]);
});

test("biểu tượng theo category của máy chủ; id lạ có ghim", () => {
  assert.equal(bieuTuongLoai("cafe"), "cafe-outline");
  assert.equal(bieuTuongLoai("di-choi-dem"), "moon-outline");
  assert.equal(bieuTuongLoai("gi-do-moi"), "location-outline");
});

test("locTheoTen không phân biệt hoa thường, tìm trong tên, loại và nét", () => {
  const cho2 = { ...CHO, id: "p-2", name: "Lưng Chừng Cafe", kinds: ["Cafe"], traits: ["View đẹp"], address: "Đồi" };
  const ds = [CHO, cho2].map((c) => ({
    ...c,
    ratingCount: c.rating_count,
    distanceKm: c.distance_km,
    priceMinVnd: c.price_min_vnd,
    priceMaxVnd: c.price_max_vnd,
    openNow: c.open_now,
    openHours: c.open_hours,
    travelMinutes: c.travel_minutes,
  }));
  assert.deepEqual(locTheoTen(ds, "CAFE view").map((p) => p.id), ["p-2"]);
  assert.deepEqual(locTheoTen(ds, "nướng").map((p) => p.id), ["p-1"]);
  assert.deepEqual(locTheoTen(ds, "nuong xom").map((p) => p.id), ["p-1"], "không dấu vẫn ra");
  assert.deepEqual(locTheoTen(ds, "Đồi").map((p) => p.id), ["p-2"], "địa chỉ cũng được tìm");
  assert.equal(locTheoTen(ds, "   ").length, 2);
});

test("câu mở cửa, dòng phụ và đường chỉ đường nói đúng số của máy chủ", () => {
  assert.equal(cauMoCua({ openNow: true, openHours: "10:00 - 22:30" }), "Đang mở · 10:00 - 22:30");
  assert.equal(cauMoCua({ openNow: false, openHours: "10:00 - 22:30" }), "Đã đóng · mở 10:00 - 22:30");
  assert.equal(dongPhu({ kinds: ["BBQ", "Lào"], travelMinutes: 25 }), "BBQ · Lào · 25 phút đi xe");
  assert.equal(dongPhu({ kinds: [], travelMinutes: 5 }), "5 phút đi xe");
  assert.equal(duongChiDuong({ lat: 11.94, lng: 108.44, name: "Xóm Lào" }), "geo:11.94,108.44?q=X%C3%B3m%20L%C3%A0o");
});

test("cauTimKiem: có kết quả thì im, mỗi kiểu thất bại một câu thật", () => {
  assert.equal(cauTimKiem({ kind: "chua-tim" }), null);
  assert.equal(cauTimKiem({ kind: "co-ket-qua", query: "x", understood: {}, places: [] }), null);
  assert.match(cauTimKiem({ kind: "khong-tra-loi", query: "x" }), /chưa đủ chắc/);
  assert.match(cauTimKiem({ kind: "qua-nhieu-lan", query: "x" }), /Hết lượt/);
  assert.match(cauTimKiem({ kind: "cau-khong-hop-le", max: 300 }), /300/);
  assert.match(cauTimKiem({ kind: "khong-noi-duoc", url: "u", detail: "d" }), /Không nối được/);
});
