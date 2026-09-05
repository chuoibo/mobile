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
  anhBiaThe,
  CAU_NGUON_ANH,
  bieuTuongLoai,
  boLuuDiaDiem,
  cauDuongDi,
  cauGia,
  cauGiayPhep,
  cauHoatDong,
  cauMoCua,
  cauNguonDuLieu,
  cauTimKiem,
  chiTietNgan,
  daoLuu,
  docAnhDiaDiem,
  docChiTiet,
  docDaLuu,
  docDanhMuc,
  dongPhu,
  duongChiDuong,
  locTheoTen,
  nguonAnhDiaDiem,
  parseAnhDiaDiem,
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
  const goi = gia(() => ({
    status: 200,
    body: {
      places: [CHO],
      categories: [{ id: "cafe", label: "Cafe" }],
      group: {},
      // M10: mỗi câu trả lời nói nó của thành phố nào.
      destination: { id: "d-da-lat", name: "Đà Lạt" },
    },
  }));
  const dm = await docDanhMuc({ category: "cafe", q: "  nướng " });
  assert.equal(dm.destination.name, "Đà Lạt");
  assert.equal(dm.places[0].name, "Tiệm Nướng Xóm Lào");
  assert.equal(dm.places[0].priceMinVnd, 200000);
  assert.deepEqual(dm.categories, [{ id: "cafe", label: "Cafe" }]);
  assert.match(goi[0].url, /\/places\?category=cafe&q=n/);
  assert.doesNotMatch(goi[0].url, /context_id/);
  assert.equal((goi[0].init.method ?? "GET").toUpperCase(), "GET");
  assert.equal(goi[0].init.headers?.Authorization, undefined, "danh mục là công khai");
});

test("docDanhMuc từ chối đồng lẻ như App B từng làm", async () => {
  gia(() => ({
    status: 200,
    body: {
      places: [{ ...CHO, price_min_vnd: 199.5 }],
      categories: [],
      destination: { id: "d-da-lat", name: "Đà Lạt" },
    },
  }));
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

/* ------------------------------------------------------------------ M9 -- */
/* Danh mục thật: cái gì không biết thì màn phải nói là chưa biết.
 *
 * Kể từ M9 (ADR-0017) địa điểm nhập từ OpenStreetMap: có tên, toạ độ, loại
 * hình — và thường KHÔNG có giá, giờ mở cửa hay đánh giá. Nhóm test này gác
 * đúng một câu: không có dữ liệu thì không được vẽ ra số.
 */

const CHO_OSM = {
  id: "osm-node-4407",
  name: "Cà Phê Sương",
  category: "cafe",
  kinds: ["Cà phê"],
  rating: null,
  ratingCount: null,
  distanceKm: null,
  priceMinVnd: null,
  priceMaxVnd: null,
  address: "6 Khu Hòa Bình, Đà Lạt",
  openNow: null,
  openHours: null,
  travelMinutes: null,
  photoCount: 0,
  photoUrl: null,
  traits: ["Wifi"],
  groupFit: null,
  flag: null,
  lat: 11.9418,
  lng: 108.4372,
  source: "osm",
  license: "ODbL-1.0",
  match: null,
};

test("chỗ không có giá không bao giờ in ra một con số", () => {
  assert.equal(cauGia(CHO_OSM), "Chưa có giá");
  assert.equal(cauGia({ priceMinVnd: 200000, priceMaxVnd: 250000 }), "200.000đ – 250.000đ mỗi người");
  assert.equal(cauGia({ priceMinVnd: 200000, priceMaxVnd: 200000 }), "200.000đ mỗi người");
});

test("giờ mở cửa có ba trạng thái, và «chưa biết» không phải «đã đóng»", () => {
  assert.equal(cauMoCua(CHO_OSM), "Chưa có giờ mở cửa");
  assert.equal(
    cauMoCua({ openNow: null, openHours: "Mo-Su 07:00-22:00" }),
    "Giờ mở cửa: Mo-Su 07:00-22:00",
  );
  assert.equal(cauMoCua({ openNow: true, openHours: "10:00 – 22:30" }), "Đang mở · 10:00 – 22:30");
  assert.equal(cauMoCua({ openNow: false, openHours: "10:00 – 22:30" }), "Đã đóng · mở 10:00 – 22:30");
});

test("hàng chi tiết chỉ vẽ những gì có; không có gì thì vẽ địa chỉ", () => {
  const chiOsm = chiTietNgan(CHO_OSM);
  assert.deepEqual(
    chiOsm.map((m) => m.icon),
    ["location-outline"],
    "chỗ OSM trần chỉ còn địa chỉ",
  );
  assert.equal(chiOsm[0].chu, "6 Khu Hòa Bình, Đà Lạt");

  const day = chiTietNgan({
    ...CHO_OSM,
    rating: 4.7,
    ratingCount: 128,
    distanceKm: 1.2,
    priceMinVnd: 200000,
    priceMaxVnd: 250000,
    openNow: true,
    openHours: "10:00 – 22:30",
  });
  assert.deepEqual(
    day.map((m) => m.icon),
    ["star", "navigate-outline", "wallet-outline", "time-outline"],
  );
  assert.equal(day[0].chu, "4.7 (128)");
});

test("không dòng nào in chữ null hay undefined", () => {
  const cau = [
    cauGia(CHO_OSM),
    cauMoCua(CHO_OSM),
    cauDuongDi(CHO_OSM),
    dongPhu(CHO_OSM),
    ...chiTietNgan(CHO_OSM).map((m) => m.chu),
  ];
  for (const c of cau) {
    assert.ok(!/null|undefined|NaN/.test(c), `«${c}» lộ giá trị rỗng`);
  }
});

test("nguồn dữ liệu được ghi cho chỗ nhập từ OSM, không ghi cho chỗ seed", () => {
  assert.equal(cauNguonDuLieu(CHO_OSM), "Dữ liệu địa điểm: OpenStreetMap (ODbL)");
  assert.equal(cauNguonDuLieu({ source: "seed", license: null }), null);
});

test("hàng chỉ đường nói được cả khi không biết xa gần", () => {
  assert.equal(cauDuongDi(CHO_OSM), "Mở bằng ứng dụng bản đồ");
  assert.equal(cauDuongDi({ distanceKm: 1.2, travelMinutes: 25 }), "1.2 km · 25 phút đi xe");
  assert.equal(cauDuongDi({ distanceKm: 1.2, travelMinutes: null }), "1.2 km");
});

test("dòng phụ bỏ phần thời gian khi máy chủ không biết", () => {
  assert.equal(dongPhu(CHO_OSM), "Cà phê");
  assert.equal(dongPhu({ kinds: ["Cà phê"], travelMinutes: 25 }), "Cà phê · 25 phút đi xe");
});

test("lọc theo tên vẫn chạy khi địa chỉ rỗng", () => {
  const khongDiaChi = { ...CHO_OSM, address: null };
  assert.equal(locTheoTen([khongDiaChi], "suong").length, 1);
  assert.equal(locTheoTen([khongDiaChi], "hoa binh").length, 0);
});

/* ── Ảnh có giấy phép và «nên làm gì» (M12) ─────────────────────────────── */

const ANH = {
  id: "0f0e0d0c-0b0a-4a9b-8c7d-6e5f4a3b2c1d",
  url: "/places/p-1/photos/0f0e0d0c-0b0a-4a9b-8c7d-6e5f4a3b2c1d",
  author: "Nguyễn A",
  license: "CC BY-SA 4.0",
  source_url: "https://commons.wikimedia.org/wiki/File:X.jpg",
  title: "Hồ Xuân Hương",
  width: 1024,
  height: 768,
};

test("ảnh thiếu tác giả, giấy phép hay nguồn bị từ chối chứ không vẽ thiếu credit", () => {
  assert.deepEqual(parseAnhDiaDiem(ANH, "photos[0]").author, "Nguyễn A");
  for (const khoa of ["author", "license", "source_url"]) {
    assert.throws(
      () => parseAnhDiaDiem({ ...ANH, [khoa]: "  " }, "photos[0]"),
      new RegExp(khoa),
      `thiếu ${khoa} phải ném`,
    );
  }
});

test("ảnh trỏ sang host khác bị từ chối: <Image> quay số cho bất kỳ địa chỉ nào nó nhận", () => {
  assert.throws(
    () => parseAnhDiaDiem({ ...ANH, url: "https://vi-du.example/anh.jpg" }, "photos[0]"),
    /địa chỉ ảnh/,
  );
});

test("docAnhDiaDiem đọc gallery công khai, không mang bearer", async () => {
  datTokenPhien("token-thu");
  const goi = gia(() => ({ status: 200, body: { place_id: "p-1", photos: [ANH] } }));
  const ds = await docAnhDiaDiem("p-1");
  assert.equal(ds.length, 1);
  assert.equal(ds[0].sourceUrl, ANH.source_url);
  assert.match(goi[0].url, /\/places\/p-1\/photos$/);
  assert.equal(goi[0].init.headers?.Authorization, undefined, "ảnh địa điểm là công khai");
});

test("nguồn ảnh là địa chỉ của chính máy chủ này, và câu giấy phép có cả hai vế", () => {
  const anh = parseAnhDiaDiem(ANH, "photos[0]");
  assert.ok(nguonAnhDiaDiem(anh).uri.endsWith(ANH.url));
  assert.equal(cauGiayPhep(anh), "Ảnh quanh đây: Nguyễn A · CC BY-SA 4.0");
});

test("thẻ chỉ vẽ ảnh bìa khi giấy phép đi cùng; thiếu một vế thì quay về dải chữ", () => {
  const co = anhBiaThe({ photoUrl: "/places/p-1/photos/a", photoAuthor: "Nguyễn A", photoLicense: "CC BY-SA 4.0" });
  assert.ok(co !== null);
  assert.equal(co.giayPhep, "Ảnh quanh đây: Nguyễn A · CC BY-SA 4.0");
  assert.equal(anhBiaThe({ photoUrl: "/places/p-1/photos/a", photoAuthor: null, photoLicense: "CC BY-SA 4.0" }), null);
  assert.equal(anhBiaThe({ photoUrl: "/places/p-1/photos/a", photoAuthor: "Nguyễn A", photoLicense: null }), null);
  assert.equal(anhBiaThe({ photoUrl: null, photoAuthor: "Nguyễn A", photoLicense: "CC BY-SA 4.0" }), null);
});

test("credit không bao giờ nói ảnh là của chính nơi này — importer tìm theo bán kính 250 m", () => {
  const anh = parseAnhDiaDiem(ANH, "photos[0]");
  assert.match(cauGiayPhep(anh), /quanh đây/);
  assert.match(CAU_NGUON_ANH, /Không phải ảnh do nơi này cung cấp/);
  assert.match(CAU_NGUON_ANH, /Wikimedia Commons/);
});

test("«nên làm gì» chỉ có tiêu đề khi máy chủ có câu; rỗng thì màn không vẽ mục nào", () => {
  assert.equal(cauHoatDong([]), null);
  assert.equal(cauHoatDong(["Ăn một bữa"]), "Nên làm gì ở đây");
});

test("docChiTiet đọc «nên làm gì» và từ chối câu rỗng", async () => {
  gia(() => ({
    status: 200,
    body: { ...CHO, description: null, reviews: [], photos_available: true, activities: ["Ăn một bữa", "Ngồi ngoài trời"] },
  }));
  const ct = await docChiTiet("p-1");
  assert.deepEqual(ct.activities, ["Ăn một bữa", "Ngồi ngoài trời"]);
  assert.equal(ct.photosAvailable, true);

  gia(() => ({ status: 200, body: { ...CHO, reviews: [], activities: ["  "] } }));
  await assert.rejects(docChiTiet("p-1"), /activities/);
});

test("chi tiết cũ không có activities vẫn đọc được: danh sách rỗng, không phải lỗi", async () => {
  gia(() => ({ status: 200, body: { ...CHO, description: null, reviews: [] } }));
  const ct = await docChiTiet("p-1");
  assert.deepEqual(ct.activities, []);
  assert.equal(ct.photosAvailable, false);
});
