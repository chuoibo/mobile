/* What a place photograph URL is allowed to be, as assertions rather than as
 * a renderer. The frame (`Anh`) needs React Native; this file only pins the
 * wire read that will one day fill it.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 */
import assert from "node:assert/strict";
import test from "node:test";

import { parsePlace } from "../dist-test/screens/kham-pha/places.js";

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

test("photo_url http/https được giữ nguyên", () => {
  assert.equal(
    parsePlace(row({ photo_url: "http://cdn.example/p.jpg" }), "p").photoUrl,
    "http://cdn.example/p.jpg",
  );
  assert.equal(
    parsePlace(row({ photo_url: "https://cdn.example/p.jpg" }), "p").photoUrl,
    "https://cdn.example/p.jpg",
  );
});

test("photo_url thiếu, null, rỗng hoặc không phải chuỗi thì ra null, không ném", () => {
  assert.equal(parsePlace(row({ photo_url: null }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: "" }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: 12 }), "p").photoUrl, null);
});

test("thiếu field photo_url không làm parsePlace ném lỗi", () => {
  const p = parsePlace(row(), "places[0]");
  assert.equal(p.photoUrl, null);
});

test("photo_url không phải http/https bị bỏ, không đưa vào <Image>", () => {
  // This value is sent by the server and goes straight into an <Image>.
  // javascript:/data:/file: must not survive the parse.
  assert.equal(parsePlace(row({ photo_url: "javascript:alert(1)" }), "p").photoUrl, null);
  // Spelled without a base64 payload on purpose. The repo guard's
  // `data-uri-base64` rule refuses inline binary anywhere in the tree and is
  // right to; the scheme is what this assertion is about, so the scheme is all
  // it needs to carry.
  assert.equal(parsePlace(row({ photo_url: "data:image/png,not-base64" }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: "file:///etc/passwd" }), "p").photoUrl, null);
});
