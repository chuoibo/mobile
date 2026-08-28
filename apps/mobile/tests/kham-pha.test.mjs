/* What the Khám phá screen is allowed to say, as assertions rather than as taps.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * The acceptance criteria for rd-do-fe-06 are a card layout, an AI MATCH badge,
 * and a reason that is genuinely generated. Layout is not checkable here and is
 * not claimed to be -- that is the `expo export` build plus `imp detect` on the
 * rendered page. What *is* checkable, and what this file exists for, is the
 * gate underneath the badge: a score nobody computed must never be able to
 * wear the words "AI MATCH", and a screen with no data must say which address
 * it tried instead of rendering an empty grid.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  byMatchThenRating,
  fetchPlaces,
  formatDistance,
  formatKinds,
  formatPriceBand,
  formatPricePerPerson,
  formatRating,
  locNoiBo,
  matchLabel,
  parseCatalogue,
  parsePlace,
  placesUrl,
} from "../dist-test/screens/kham-pha/places.js";

/** One wire row, valid, that individual tests bend to make a point. */
function row(over = {}) {
  return {
    id: "p-1",
    name: "Tiệm Nướng Xóm Lào",
    category: "quan-an-local",
    kinds: ["BBQ", "Lào", "Local"],
    rating: 4.7,
    rating_count: 128,
    distance_km: 1.2,
    price_min_vnd: 200000,
    price_max_vnd: 250000,
    address: "27/1 Yersin, P.10, TP. Đà Lạt",
    open_now: true,
    open_hours: "10:00 – 22:30",
    travel_minutes: 25,
    photo_count: 18,
    traits: ["Chill", "View đẹp"],
    group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè" },
    flag: null,
    lat: 11.9404,
    lng: 108.4383,
    match: {
      score: 95,
      source: "ai",
      verdict: "hop",
      reason: "Hợp vì ngân sách và đồ nướng.",
      factors: [],
    },
    ...over,
  };
}

function res(body, { status = 200, ok = true } = {}) {
  return {
    ok,
    status,
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  };
}

/* --------------------------------------------------- the badge gate ------ */

test("chỉ điểm do model chấm mới được mang chữ AI MATCH", () => {
  const label = matchLabel({ score: 95, source: "ai", verdict: "hop", reason: "vì …", factors: [] });
  assert.deepEqual(label, { text: "AI MATCH 95%", real: true });
});

test("nguồn `stub` không còn là giá trị hợp lệ", () => {
  // The dev stub server this once described is gone; `GET /places` is a real
  // route now. Leaving `stub` in the union would keep a door open for a canned
  // sentence to arrive claiming a provenance nothing on the server can produce
  // -- and the parser is the only place that door can be shut.
  assert.throws(
    () => parsePlace(row({ match: { score: 95, source: "stub", reason: "câu mẫu", factors: [] } }), "p"),
    /source phải là ai\|none/,
  );
});

test("điểm không có AI đứng sau KHÔNG được mang chữ AI MATCH", () => {
  // rd-be-05's brief: "nếu là số giả thì đừng hiện phần trăm". The server
  // sends `source: "none"` when Gemini answered for nobody; the screen renders
  // `real: false` as a neutral chip so nobody reads it as a model score.
  const label = matchLabel({ score: 95, source: "none", verdict: null, reason: "máy tính", factors: [] });
  assert.equal(label.real, false);
  assert.ok(!label.text.includes("AI MATCH"), `nhãn không AI không được chứa AI MATCH: ${label.text}`);
});

test("AI nói không hợp thì không hiện phần trăm nào cả", () => {
  // A percentage next to the words "chưa hợp" is noise: it invites the reader
  // to weigh a number against a conclusion that already accounts for it. The
  // model's own answer wins, and the score stays in the detail sheet.
  const label = matchLabel({ score: 82, source: "ai", verdict: "khong-hop", reason: "quá xa", factors: [] });
  assert.equal(label.real, true);
  assert.ok(!label.text.includes("%"), `nhãn 'chưa hợp' không được kèm phần trăm: ${label.text}`);
  assert.ok(!label.text.includes("AI MATCH"), label.text);
});

test("AI nói tạm được thì nói tạm được, không nâng thành MATCH", () => {
  const label = matchLabel({ score: 81, source: "ai", verdict: "tam", reason: "thiếu đồ nướng", factors: [] });
  assert.equal(label.real, true);
  assert.ok(!label.text.includes("AI MATCH"), label.text);
  assert.ok(label.text.includes("81%"), label.text);
});

test("không có match thì không có huy hiệu nào cả", () => {
  assert.equal(matchLabel(null), null);
});

test("verdict lạ bị từ chối chứ không lọt xuống màn hình", () => {
  assert.throws(
    () => parsePlace(row({ match: { score: 90, source: "ai", verdict: "tuyet-voi", reason: "x", factors: [] } }), "p"),
    /verdict phải là hop\|tam\|khong-hop\|null/,
  );
});

test("source và verdict phải nói cùng một chuyện", () => {
  // `source: "ai"` with no verdict, or a verdict with no model behind it,
  // means the two halves of the server disagree about whether Gemini spoke.
  // Either way the badge would be decided by a coin toss, so refuse instead.
  assert.throws(
    () => parsePlace(row({ match: { score: 90, source: "ai", verdict: null, reason: "x", factors: [] } }), "p"),
    /source=ai nhưng verdict=null/,
  );
  assert.throws(
    () => parsePlace(row({ match: { score: 90, source: "none", verdict: "hop", reason: "x", factors: [] } }), "p"),
    /source=none nhưng verdict="hop"/,
  );
});

/* ------------------------------------------------ money law 1 ------------ */

test("khoảng giá lẻ đồng bị từ chối chứ không làm tròn cho đẹp", () => {
  // Integer đồng is money law 1, and it reaches the read path too: a screen
  // that rounds 249500 into "250k" has invented a number nobody agreed to.
  assert.throws(
    () => parsePlace(row({ price_min_vnd: 249500.5 }), "places[0]"),
    /price_min_vnd phải là số nguyên đồng/,
  );
});

test("khoảng giá ngược bị từ chối", () => {
  assert.throws(() => parsePlace(row({ price_min_vnd: 300000, price_max_vnd: 200000 }), "p"), /ngược/);
});

test("số tiền hiện ra đúng dạng nghìn, không đẻ ra chữ số nào", () => {
  assert.equal(formatPriceBand(200000, 250000), "200–250k");
  assert.equal(formatPriceBand(250000, 250000), "250k");
  assert.equal(formatPricePerPerson(180000, 230000), "~180–230k/người");
});

/* ------------------------------------------------ parsing --------------- */

test("một dòng hợp lệ đọc ra đủ các trường màn hình cần", () => {
  const p = parsePlace(row(), "places[0]");
  assert.equal(p.name, "Tiệm Nướng Xóm Lào");
  assert.equal(p.priceMinVnd, 200000);
  assert.equal(p.groupFit.maxPeople, 10);
  assert.equal(p.match.source, "ai");
  assert.equal(p.flag, null);
});

test("trường thiếu được gọi tên, không im lặng thành undefined", () => {
  // A screen that renders `undefined` for a rating looks like a CSS bug and
  // gets chased in the wrong file; a refusal that names the field is read once.
  assert.throws(() => parsePlace(row({ rating: null }), "places[3]"), /places\[3\]\.rating/);
});

test("source lạ bị từ chối — không có đường nào cho nhãn tự chế", () => {
  assert.throws(() => parsePlace(row({ match: { ...row().match, source: "magic" } }), "p"), /source/);
});

test("flag chỉ được là new, hot hoặc rỗng", () => {
  assert.equal(parsePlace(row({ flag: "hot" }), "p").flag, "hot");
  assert.throws(() => parsePlace(row({ flag: "sale" }), "p"), /flag/);
});

test("catalogue thiếu mảng places bị từ chối", () => {
  assert.throws(() => parseCatalogue({ categories: [] }), /places/);
});

/* ------------------------------------------------ the four failures ----- */

test("404 là 'route chưa dựng', không phải 'lỗi'", async () => {
  const s = await fetchPlaces({ base: "http://x.invalid", fetchImpl: async () => res("", { status: 404, ok: false }) });
  assert.equal(s.kind, "chua-co-endpoint");
  assert.match(s.work, /rd-be-05/);
  assert.match(s.url, /\/places\?/);
});

test("không nối được máy chủ thì nói địa chỉ đã thử", async () => {
  const s = await fetchPlaces({
    base: "http://localhost:9",
    fetchImpl: async () => {
      throw new Error("ECONNREFUSED");
    },
  });
  assert.equal(s.kind, "khong-noi-duoc");
  assert.match(s.url, /localhost:9/);
  assert.match(s.detail, /ECONNREFUSED/);
});

test("máy chủ 500 là trạng thái riêng, kèm mã", async () => {
  const s = await fetchPlaces({ base: "http://x", fetchImpl: async () => res("boom", { status: 500, ok: false }) });
  assert.equal(s.kind, "may-chu-loi");
  assert.equal(s.status, 500);
});

test("dữ liệu sai dạng bị từ chối chứ không vẽ ra số sai", async () => {
  const s = await fetchPlaces({
    base: "http://x",
    fetchImpl: async () => res({ places: [row({ rating: "bốn phẩy bảy" })] }),
  });
  assert.equal(s.kind, "du-lieu-sai");
  assert.match(s.detail, /rating/);
});

test("trả về đúng thì ra danh sách đã đọc", async () => {
  const s = await fetchPlaces({
    base: "http://x",
    fetchImpl: async () => res({ categories: [{ id: "cafe", label: "Cafe" }], places: [row()] }),
  });
  assert.equal(s.kind, "co-du-lieu");
  assert.equal(s.places.length, 1);
  assert.equal(s.categories[0].label, "Cafe");
});

test("fetchPlaces không bao giờ ném — một tab trắng là kiểu hỏng tệ nhất", async () => {
  const s = await fetchPlaces({
    base: "http://x",
    fetchImpl: async () => {
      throw new TypeError("Failed to fetch");
    },
  });
  assert.equal(s.kind, "khong-noi-duoc");
});

/* ------------------------------------------------ query + sort + filter - */

test("URL mang theo nhóm đang xem và danh mục đang chọn", () => {
  const url = placesUrl("http://api/", { category: "cafe", q: "  view  " });
  assert.match(url, /^http:\/\/api\/places\?/);
  assert.match(url, /context_id=1aa00000/);
  assert.match(url, /category=cafe/);
  assert.match(url, /q=view/);
});

test("chỗ điểm cao lên trước, chỗ chưa chấm xuống cuối", () => {
  const mk = (id, score, rating) => ({
    id,
    rating,
    match: score === null ? null : { score, source: "ai", reason: "r", factors: [] },
  });
  const sorted = [mk("a", 60, 4.0), mk("b", null, 4.9), mk("c", 95, 4.1)].sort(byMatchThenRating);
  assert.deepEqual(sorted.map((p) => p.id), ["c", "a", "b"]);
});

test("tìm tại chỗ nhìn cả tên, loại, đặc điểm và địa chỉ", () => {
  const places = [
    parsePlace(row(), "p"),
    parsePlace(
      row({ id: "p-2", name: "An Cafe", traits: ["Vintage"], address: "63 Phan Đình Phùng, P.2" }),
      "p",
    ),
  ];
  assert.equal(locNoiBo(places, "vintage").length, 1);
  assert.equal(locNoiBo(places, "yersin").length, 1);
  assert.equal(locNoiBo(places, "").length, 2);
  assert.equal(locNoiBo(places, "không có gì").length, 0);
});

/* ------------------------------------------------ formatting ------------ */

test("khoảng cách và đánh giá đọc được", () => {
  assert.equal(formatDistance(1.24), "1.2km");
  assert.equal(formatDistance(12.6), "13km");
  assert.equal(formatRating(4.7, 128), "4.7 (128)");
  assert.equal(formatKinds(["BBQ", "Lào"]), "BBQ · Lào");
  assert.equal(formatKinds(["BBQ"]), "BBQ", "một loại thì không có dấu chấm thừa");
});
