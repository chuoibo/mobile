/* Khi máy chủ cắt bớt thẻ AI, màn hình phải NÓI RA (bug-223917).
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/lich-trinh-bi-cat.test.mjs
 *
 * `_ground_itinerary` giữ 6 chặng và vứt phần đuôi. PR #181 làm máy chủ trung
 * thực: nó cộng thêm `omitted_stop_count` (thẻ itinerary) và
 * `omitted_place_count` (thẻ places), CHỈ khi thực sự có cắt. Trước PR này màn
 * chat vẽ 6 chặng và im lặng, nên nhóm hỏi "ghi rõ từng khung giờ của cả hai
 * ngày" đọc được một ngày và tin đó là toàn bộ kế hoạch.
 *
 * Ba nhóm ca, và nhóm thứ hai là nhóm dễ mất nhất:
 *
 *  1. CÓ CẮT thì phải nói. Kiểm trên markup react-native-web thật chứ không
 *     chỉ trên parser, vì một trường được parse đúng mà không component nào
 *     vẽ ra thì người dùng vẫn không thấy gì, và ca parser vẫn xanh.
 *  2. KHÔNG CẮT thì phải im. Thẻ ngắn không mang key này, nên một hiện thực
 *     đọc thẳng `payload.omitted_stop_count` rồi vẽ sẽ in "còn 0 chặng nữa"
 *     hoặc "còn undefined chặng nữa". Không có vế này thì "báo đúng lúc cắt"
 *     và "báo lung tung" xanh y hệt nhau.
 *  3. Cả THẺ trong luồng chat lẫn MÀN CHI TIẾT. Màn chi tiết là chỗ người ta
 *     bấm vào để đọc "cả kế hoạch"; im lặng ở đó là đúng con bug này, chỉ sâu
 *     hơn một cú bấm.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { keHoachTuCard, theTuCard } from "../dist-test/screens/chat/ke-hoach.js";
import { TheKeHoach } from "../dist-test/screens/chat/TheKeHoach.js";
import { ChiTietKeHoach } from "../dist-test/screens/chat/ChiTietKeHoach.js";

function diaDiem(i) {
  return {
    id: `11111111-aaaa-4bbb-8ccc-00000000a00${i}`,
    name: `Quán số ${i}`,
    address: `${i} Nguyễn Huệ`,
  };
}

function chang(i) {
  return { time_text: `0${i}:00`, note: null, place: diaDiem(i) };
}

/** Thẻ lịch trình do máy chủ trả về: `soChang` chặng còn lại, và
 *  `omitted_stop_count` chỉ được cộng thêm khi gọi có truyền. */
function theLichTrinh(soChang, them = {}) {
  const stops = [];
  for (let i = 1; i <= soChang; i++) stops.push(chang(i));
  return { kind: "itinerary", payload: { title: "Đà Lạt hai ngày", stops, ...them } };
}

function theDiaDiem(soCho, them = {}) {
  const places = [];
  for (let i = 1; i <= soCho; i++) places.push(diaDiem(i));
  return { kind: "places", payload: { intro: "Vài chỗ gần bạn", places, ...them } };
}

/** Markup react-native-web sinh ra, dạng chuỗi phẳng để so khớp câu chữ.
 *  Thực thể HTML được trả về dạng ký tự để "chỗ" không thành "ch&#x1EE3;". */
function veRa(element) {
  return renderToStaticMarkup(element).replace(/&#x([0-9A-Fa-f]+);/g, (_, hex) =>
    String.fromCodePoint(Number.parseInt(hex, 16)),
  );
}

function veThe(card) {
  return veRa(React.createElement(TheKeHoach, { card, onXemChiTiet: () => {} }));
}

/* -------------------------------------------------- parser ---------------- */

test("thẻ lịch trình bị cắt mang theo số chặng đã mất", () => {
  const the = theTuCard(theLichTrinh(6, { omitted_stop_count: 2 }));
  assert.equal(the.kind, "itinerary");
  assert.equal(the.chang.length, 6);
  assert.equal(the.soChangBiCat, 2);
});

test("thẻ lịch trình đủ chặng không mang số nào", () => {
  const the = theTuCard(theLichTrinh(3));
  assert.equal(the.soChangBiCat, undefined);
});

test("thẻ địa điểm bị cắt mang theo số chỗ đã mất", () => {
  const the = theTuCard(theDiaDiem(6, { omitted_place_count: 3 }));
  assert.equal(the.kind, "places");
  assert.equal(the.soChoBiCat, 3);
});

test("thẻ địa điểm đủ chỗ không mang số nào", () => {
  assert.equal(theTuCard(theDiaDiem(2)).soChoBiCat, undefined);
});

test("keHoachTuCard giữ nguyên số chặng bị cắt", () => {
  assert.equal(keHoachTuCard(theLichTrinh(6, { omitted_stop_count: 4 })).soChangBiCat, 4);
});

/* Hợp đồng nói `int > 0`. Máy chủ hôm nay giữ đúng, nhưng client đọc một dict
 * tự do trên dây: một `0` lọt qua sẽ thành câu "còn 0 chặng nữa", và một `2.5`
 * hay `"2"` thành "còn 2.5 chặng nữa". Cả ba đều tệ hơn im lặng. */
for (const xau of [0, -1, 2.5, "2", null, true, Number.NaN, Infinity]) {
  test(`omitted_stop_count = ${String(xau)} bị bỏ qua chứ không vẽ ra`, () => {
    const the = theTuCard(theLichTrinh(6, { omitted_stop_count: xau }));
    assert.equal(the.soChangBiCat, undefined);
    const markup = veThe(theLichTrinh(6, { omitted_stop_count: xau }));
    assert.ok(!markup.includes("chặng nữa"), `vẽ ra câu bị cắt với giá trị ${String(xau)}`);
  });

  test(`omitted_place_count = ${String(xau)} bị bỏ qua chứ không vẽ ra`, () => {
    const the = theTuCard(theDiaDiem(6, { omitted_place_count: xau }));
    assert.equal(the.soChoBiCat, undefined);
    const markup = veThe(theDiaDiem(6, { omitted_place_count: xau }));
    assert.ok(!markup.includes("chỗ nữa"), `vẽ ra câu bị cắt với giá trị ${String(xau)}`);
  });
}

/* ------------------------------------------- thẻ trong luồng chat --------- */

test("thẻ lịch trình bị cắt nói ra số chặng còn thiếu", () => {
  const markup = veThe(theLichTrinh(6, { omitted_stop_count: 2 }));
  assert.ok(markup.includes("còn 2 chặng nữa"), markup);
});

test("thẻ lịch trình đủ chặng không nói gì về chuyện bị cắt", () => {
  const markup = veThe(theLichTrinh(3));
  assert.ok(!markup.includes("chặng nữa"), markup);
  assert.ok(!markup.includes("rút gọn"), markup);
});

test("thẻ địa điểm bị cắt nói ra số chỗ còn thiếu", () => {
  const markup = veThe(theDiaDiem(6, { omitted_place_count: 3 }));
  assert.ok(markup.includes("còn 3 chỗ nữa"), markup);
});

test("thẻ địa điểm đủ chỗ không nói gì về chuyện bị cắt", () => {
  const markup = veThe(theDiaDiem(2));
  assert.ok(!markup.includes("chỗ nữa"), markup);
  assert.ok(!markup.includes("rút gọn"), markup);
});

/* Thẻ trong luồng chat vốn chỉ vẽ 3 chặng đầu rồi mời bấm "Xem chi tiết". Câu
 * cảnh báo phải nói về phần MÁY CHỦ ĐÃ VỨT, không phải phần đang nằm sau nút
 * bấm, nếu không nó dạy người ta rằng bấm vào là thấy đủ. */
test("câu cảnh báo nói rõ phần bị mất không nằm sau nút xem chi tiết", () => {
  const markup = veThe(theLichTrinh(6, { omitted_stop_count: 2 }));
  assert.ok(markup.includes("Xem chi tiết kế hoạch"), "vẫn phải có nút cũ");
  assert.ok(markup.includes("chưa được gửi"), markup);
});

/* ------------------------------------------------ màn chi tiết ------------ */

test("màn chi tiết của kế hoạch bị cắt cũng nói ra", () => {
  const keHoach = keHoachTuCard(theLichTrinh(6, { omitted_stop_count: 2 }));
  const markup = veRa(React.createElement(ChiTietKeHoach, { keHoach, onBack: () => {} }));
  assert.ok(markup.includes("còn 2 chặng nữa"), markup);
});

test("màn chi tiết của kế hoạch đủ chặng im lặng", () => {
  const keHoach = keHoachTuCard(theLichTrinh(3));
  const markup = veRa(React.createElement(ChiTietKeHoach, { keHoach, onBack: () => {} }));
  assert.ok(!markup.includes("chặng nữa"), markup);
});

/* -------------------------------------------------- câu chữ --------------- */

/* Cùng luật với `dau-gach-dai`: câu người dùng đọc không mang em-dash, và
 * không để lọt tên trường tiếng Anh của máy chủ ra màn hình. */
test("câu cảnh báo không lộ tên trường của máy chủ và không có em-dash", () => {
  for (const markup of [
    veThe(theLichTrinh(6, { omitted_stop_count: 2 })),
    veThe(theDiaDiem(6, { omitted_place_count: 3 })),
  ]) {
    assert.ok(!markup.includes("omitted"), markup);
    assert.ok(!markup.includes("—"), markup);
  }
});
