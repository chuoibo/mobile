/* Render the F34 budget card to a real HTML page, for `imp detect` to scan.
 *
 * Not a test and not shipped: this is the measuring rig for the detector.
 * `renderToStaticMarkup` alone emits class names with no stylesheet, so every
 * colour would resolve to nothing and the contrast rules -- the ones that
 * actually matter for a warning drawn in red -- would silently pass. RNW's
 * `AppRegistry.getApplication` returns the markup AND the generated CSS, which
 * is what the Expo web build ships, so the page below has the same computed
 * colours the phone browser gets.
 *
 * All four states are on one page on purpose: the detector measures rendered
 * geometry, and the over-budget card has to be legible sitting next to the
 * ordinary one rather than only in isolation.
 */
import { writeFileSync } from "node:fs";
import React from "react";
// react-native-web directly, never "react-native": this file is not compiled
// through the step that rewrites that specifier, and the real package ships
// Flow syntax node cannot parse.
import { AppRegistry, View } from "react-native-web";

import { TheBuoi } from "../dist-test/screens/len-plan/LenPlan.js";
// The real screen chrome, with the same title and hint LenPlan passes. Cards on
// a bare page measure as a flatter type scale than the screen actually has,
// because the largest step lives in `Screen`'s heading -- a finding the rig
// would have invented rather than found.
import { Screen } from "../dist-test/ui/Kit.js";

const BUOI = {
  id: "b1",
  context_id: "c1",
  created_by_id: "p1",
  title: "Đà Lạt cuối tuần",
  starts_on: "2026-09-05",
  ends_on: "2026-09-07",
  headcount: 5,
  budget_per_person_vnd: 1_200_000,
  created_at: "2026-08-29T10:00:00Z",
  stops: [],
};

const NGUON = [
  { kind: "co", vnd: 4_500_000 },
  { kind: "co", vnd: 7_200_000 },
  { kind: "chua-xong" },
  { kind: "khong-doc-duoc" },
];

function Trang() {
  return React.createElement(
    Screen,
    { title: "Lên plan", hint: "Chuyến đi của nhóm, ngày giờ và ai đi." },
    React.createElement(
      View,
      { style: { gap: 16 } },
      NGUON.map((nguon, i) =>
        React.createElement(TheBuoi, { key: i, buoi: BUOI, nguon, onMo: () => {} }),
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
<title>Ý thức ngân sách trên thẻ chuyến</title>
${renderToStaticMarkup(getStyleElement())}
</head>
<body>${renderToStaticMarkup(element)}</body>
</html>`;

writeFileSync(process.argv[2], html);
console.log(`viết ${process.argv[2]} (${html.length} byte)`);
