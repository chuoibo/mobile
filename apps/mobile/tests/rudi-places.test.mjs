import assert from "node:assert/strict";
import test from "node:test";

import { filterPlaces } from "../dist-test/rudi/places.js";
import { visibleVoteTallies } from "../dist-test/rudi/vote.js";

const PLACES = [
  { id: "a", name: "Tiệm Nướng Xóm Lèo", subtitle: "nướng", tags: ["Chill"], category: "Quán ăn", match: 95, distance: "1,2 km" },
  { id: "b", name: "Still Cafe Đà Lạt", subtitle: "cà phê", tags: ["Cà phê"], category: "Cafe", match: 92, distance: "1,8 km" },
  { id: "c", name: "Puppy Farm", subtitle: "cún", tags: ["Động vật"], category: "Vui chơi", match: 88, distance: "3,4 km" },
  { id: "d", name: "Chợ đêm", subtitle: "đêm", tags: ["Đi đêm"], category: "Đi chơi đêm", match: 80, distance: "900 m" },
  { id: "e", name: "The Coffee Hill", subtitle: "view", tags: ["Cà phê"], category: "Cafe", match: 91, distance: "2,1 km" },
  { id: "f", name: "Bánh căn Lệ", subtitle: "local", tags: ["Món local"], category: "Quán ăn", match: 86, distance: "900 m" },
  { id: "g", name: "Lẩu gà", subtitle: "lẩu", tags: ["Lẩu"], category: "Quán ăn", match: 91, distance: "1,6 km" },
  { id: "h", name: "Tiệm trà sương", subtitle: "trà", tags: ["Trà"], category: "Cafe", match: 84, distance: "1,1 km" },
  { id: "i", name: "Đồi săn mây", subtitle: "mây", tags: ["Ngoài trời"], category: "Vui chơi", match: 90, distance: "4,0 km" },
  { id: "j", name: "Thung lũng tình yêu", subtitle: "vườn", tags: ["Vườn"], category: "Vui chơi", match: 85, distance: "5,2 km" },
  { id: "k", name: "Phố đi bộ đêm", subtitle: "phố", tags: ["Đi đêm"], category: "Đi chơi đêm", match: 78, distance: "1,0 km" },
  { id: "l", name: "Hồ Tuyền Lâm đêm", subtitle: "hồ", tags: ["BBQ"], category: "Đi chơi đêm", match: 89, distance: "4,2 km" },
];

test("Cafe is a real subset, not the whole catalogue of 12", () => {
  assert.equal(PLACES.length, 12);
  const cafes = filterPlaces(PLACES, { category: "Cafe" });
  assert.ok(cafes.length > 0);
  assert.ok(cafes.length < 12);
  assert.ok(cafes.every((place) => place.category === "Cafe"));
  const all = filterPlaces(PLACES, {});
  assert.equal(all.length, 12);
});

test("query, match, near, and saved filters compose", () => {
  const nearMatch = filterPlaces(PLACES, { matchOnly: true, nearOnly: true });
  assert.ok(nearMatch.every((place) => place.match >= 90));
  const saved = filterPlaces(PLACES, { savedOnly: true, savedIds: ["b"] });
  assert.deepEqual(
    saved.map((place) => place.id),
    ["b"],
  );
  const query = filterPlaces(PLACES, { query: "xom leo" });
  assert.equal(query.length, 1);
  assert.equal(query[0].id, "a");
});

test("vote tallies stay empty until the ballot is confirmed", () => {
  assert.deepEqual(visibleVoteTallies(3, 1, false), [0, 0, 0]);
  assert.deepEqual(visibleVoteTallies(3, null, true), [0, 0, 0]);
  assert.deepEqual(visibleVoteTallies(3, 1, true), [0, 1, 0]);
});
