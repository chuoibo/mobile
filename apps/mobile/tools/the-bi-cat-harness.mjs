/* Render the truncated AI card to a real HTML page, for `imp detect` to scan.
 *
 * Not a test and not shipped: this is the measuring rig for the detector, and
 * it follows `ngan-sach-harness.mjs` for the same reason that file gives.
 * `renderToStaticMarkup` alone emits class names with no stylesheet, so every
 * colour resolves to nothing and the contrast rules pass in silence. That is
 * exactly the wrong failure here, because the whole warning this rig exists to
 * measure is drawn in `warn` orange on `card` white, and "is that legible" is
 * the question. `AppRegistry.getApplication` returns the markup AND the CSS
 * the Expo web build ships, so the page below has the computed colours a phone
 * browser actually gets.
 *
 * Both the CUT and the UNCUT state are on the page. The uncut card is not
 * padding: a warning that only reads well in isolation is a warning that will
 * be missed sitting next to the ordinary card it has to stand out from, and
 * the detector measures rendered geometry, not intent.
 */
import { writeFileSync } from "node:fs";
import React from "react";
// react-native-web directly, never "react-native": this file is not compiled
// through the step that rewrites that specifier, and the real package ships
// Flow syntax node cannot parse.
import { AppRegistry, View } from "react-native-web";

import { TheKeHoach } from "../dist-test/screens/chat/TheKeHoach.js";
import { ChiTietKeHoach } from "../dist-test/screens/chat/ChiTietKeHoach.js";
import { keHoachTuCard } from "../dist-test/screens/chat/ke-hoach.js";
import { Screen } from "../dist-test/ui/Kit.js";

function diaDiem(i) {
  return {
    id: `11111111-aaaa-4bbb-8ccc-00000000a00${i}`,
    name: ["Bánh căn Nhà Chung", "Cà phê Túi Mơ To", "Chợ đêm Đà Lạt", "Hồ Tuyền Lâm",
      "Nem nướng Bà Hùng", "Ga Đà Lạt"][i - 1],
    address: `${i} Nguyễn Chí Thanh, Phường 1`,
    price_min_vnd: 45_000 * i,
    price_max_vnd: 90_000 * i,
  };
}

function chang(i) {
  return {
    time_text: ["07:30", "09:00", "11:30", "14:00", "17:00", "19:30"][i - 1],
    note: i === 1 ? "Đi sớm cho khỏi phải xếp hàng" : null,
    place: diaDiem(i),
  };
}

const STOPS = [1, 2, 3, 4, 5, 6].map(chang);
const PLACES = [1, 2, 3, 4, 5, 6].map(diaDiem);

/** The card the server sends when it kept 6 of 8 stops. */
const CAT = {
  kind: "itinerary",
  payload: { title: "Đà Lạt hai ngày", stops: STOPS, omitted_stop_count: 2 },
};
/** The same card when nothing was cut. Carries neither key. */
const KHONG_CAT = {
  kind: "itinerary",
  payload: { title: "Chiều thứ bảy loanh quanh", stops: STOPS.slice(0, 3) },
};
const CHO_CAT = {
  kind: "places",
  payload: { intro: "Vài chỗ ăn tối gần chỗ mình ở", places: PLACES, omitted_place_count: 3 },
};

function Trang() {
  return React.createElement(
    Screen,
    { title: "Nhóm chat", hint: "Rủ Đi AI trả lời trong nhóm." },
    React.createElement(
      View,
      { style: { gap: 16 } },
      React.createElement(TheKeHoach, { card: CAT, onXemChiTiet: () => {} }),
      React.createElement(TheKeHoach, { card: KHONG_CAT, onXemChiTiet: () => {} }),
      React.createElement(TheKeHoach, { card: CHO_CAT, onXemChiTiet: () => {} }),
      React.createElement(
        View,
        { style: { height: 900 } },
        React.createElement(ChiTietKeHoach, { keHoach: keHoachTuCard(CAT), onBack: () => {} }),
      ),
    ),
  );
}

AppRegistry.registerComponent("Trang", () => Trang);
const { element, getStyleElement } = AppRegistry.getApplication("Trang", {});
const { renderToStaticMarkup } = await import("react-dom/server");

const html = `<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thẻ AI nói ra khi máy chủ đã cắt bớt</title>
${renderToStaticMarkup(getStyleElement())}
</head>
<body>${renderToStaticMarkup(element)}</body>
</html>`;

writeFileSync(process.argv[2], html);
console.log(`viết ${process.argv[2]} (${html.length} byte)`);
