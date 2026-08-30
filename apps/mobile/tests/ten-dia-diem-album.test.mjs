/* A place the server could not name must not be shown to the group as its id.
 *
 * `Album.places[]` is `{ place_id, place_name: string | null }` -- the null is
 * in the wire type (`album-api.ts`), in the response schema
 * (`services/api/app/api/schemas.py`, `place_name: str | None`), and in the
 * domain that fills it: `_text()` in `services/api/app/domain/album.py` returns
 * `None` for a name that is missing, not a string, or blank after stripping.
 * So a check-in saved with no place name, or with `"   "`, arrives as null by
 * design and not by accident.
 *
 * The "Đã tới" card wrote `p.place_name ?? p.place_id`, so that null fell
 * through to the id and the trip album read:
 *
 *     Đã tới
 *     · 4f1e2d3c-9a8b-4c7d-8e6f-0a1b2c3d4e5f
 *
 * The reel, on the same screen, already handles the same null correctly
 * (`canh.place_name ? ... : ""`). One screen printing a raw identifier where
 * the other prints nothing is the drift this file pins shut.
 *
 * What is pinned here is narrow on purpose: no id reaches the reader, and the
 * row still says something a person can read. It does NOT pin "the right place
 * name is shown" -- with a null on the wire the client has no way to know one,
 * exactly as `ten-nguoi-la.test.mjs` reasons about `TEN_CHUA_BIET` for people.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MotAlbum } from "../dist-test/screens/album/AlbumChuyenDi.js";
import { TEN_DIA_DIEM_CHUA_BIET } from "../dist-test/screens/album/album-api.js";

/** Markup with tags stripped, which is what a person actually reads. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

const KHONG_TEN = "4f1e2d3c-9a8b-4c7d-8e6f-0a1b2c3d4e5f";
const CO_TEN = "8c7b6a59-3d2e-4f1a-9b8c-7d6e5f4a3b2c";
const NGUOI_XEM = "1aa0be7f-9c3d-4e1a-8b2f-a7c5d9e3f1b6";

function album(places) {
  return {
    context_id: "2bb1cf80-ad4e-4f2b-9c3a-b8d6ea04c2f7",
    outing_id: "3cc2da91-be5f-4a3c-8d4f-c9e7fb15d3a8",
    title: "Đà Lạt cuối tuần",
    period_label: "2026",
    starts_on: "2026-08-14",
    ends_on: "2026-08-16",
    in_progress: false,
    photos: [],
    photo_count: 0,
    places,
    place_count: places.length,
    checkin_count: places.length,
    highlights: [],
    split_total_vnd: 1_240_000,
    expense_count: 3,
    headcount: 5,
  };
}

/* Rendered through the real screen component rather than through a naming
 * helper called directly: a helper can go on returning the right word long
 * after the card has stopped calling it. */
function doc(places) {
  return words(
    React.createElement(MotAlbum, {
      album: album(places),
      nguoiXem: NGUOI_XEM,
      onXemPhim: () => {},
    }),
  );
}

test("địa điểm không có tên thì không in id của nó ra màn hình", () => {
  const read = doc([{ place_id: KHONG_TEN, place_name: null }]);
  assert.ok(!read.includes(KHONG_TEN), `id lọt ra màn hình: ${read}`);
  assert.ok(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/.test(read), `UUID lọt ra màn hình: ${read}`);
});

test("chỗ đặt tên địa điểm có một từ người đọc hiểu, không phải ô trống", () => {
  const read = doc([{ place_id: KHONG_TEN, place_name: null }]);
  assert.ok(read.includes("Đã tới"), `mất cả thẻ "Đã tới": ${read}`);
  assert.ok(read.includes(TEN_DIA_DIEM_CHUA_BIET), `thiếu "${TEN_DIA_DIEM_CHUA_BIET}": ${read}`);
});

/* `_text()` strips before deciding, so a blank name never leaves the server as
 * `"   "`. This asserts the client does not undo that by treating a blank
 * string as a name -- an empty bullet reads as a rendering bug, not as a place
 * nobody named. */
test("tên toàn khoảng trắng cũng không được coi là tên", () => {
  const read = doc([{ place_id: KHONG_TEN, place_name: "   " }]);
  assert.ok(!read.includes(KHONG_TEN), `id lọt ra màn hình: ${read}`);
  assert.ok(read.includes(TEN_DIA_DIEM_CHUA_BIET), `thiếu "${TEN_DIA_DIEM_CHUA_BIET}": ${read}`);
});

test("địa điểm có tên thì vẫn hiện đúng tên của nó", () => {
  const read = doc([{ place_id: CO_TEN, place_name: "Quán Gió" }]);
  assert.ok(read.includes("Quán Gió"), `mất tên thật: ${read}`);
  assert.ok(!read.includes(TEN_DIA_DIEM_CHUA_BIET), `đè lên tên thật: ${read}`);
  assert.ok(!read.includes(CO_TEN), `id lọt ra màn hình: ${read}`);
});

/* A trip can hold both kinds at once, and the named one must not be dropped
 * while the unnamed one is being handled. */
test("một chuyến có cả hai loại thì giữ nguyên cả hai dòng", () => {
  const read = doc([
    { place_id: CO_TEN, place_name: "Quán Gió" },
    { place_id: KHONG_TEN, place_name: null },
  ]);
  assert.ok(read.includes("Quán Gió"), `mất địa điểm có tên: ${read}`);
  assert.ok(read.includes(TEN_DIA_DIEM_CHUA_BIET), `mất địa điểm chưa có tên: ${read}`);
  assert.ok(!read.includes(KHONG_TEN), `id lọt ra màn hình: ${read}`);
});
