/* Render the two Khám phá error cards to a real HTML page, for `imp detect`.
 *
 * Not a test and not shipped: this is the measuring rig for the detector, same
 * shape and same reason as `ngan-sach-harness.mjs`. `renderToStaticMarkup`
 * alone emits class names with no stylesheet, so every colour resolves to
 * nothing and the contrast rules pass in silence. RNW's
 * `AppRegistry.getApplication` returns the markup AND the generated CSS, which
 * is what the Expo web build ships, so this page has the same computed colours
 * a phone browser gets.
 *
 * What it is measuring here, specifically: bug-185426 replaced a raw server
 * body with a Vietnamese sentence plus a labelled excerpt, which makes the body
 * text of these cards several times longer than it was. Longer copy is exactly
 * what pushes a card into overflow, a clipped container, or a line-length
 * finding -- none of which the markup assertions in
 * `tests/loi-may-chu-web.test.mjs` can see.
 *
 * All six states share one page, and the page is wrapped in the real `Screen`
 * with the title Khám phá passes. Bare cards on an empty page measure as a
 * flatter type scale than the screen has, because the largest step lives in
 * `Screen`'s heading -- a finding the rig would have invented rather than found.
 *
 * Usage, from apps/mobile, after `tsc -p tsconfig.test.json && node tools/fixup-esm.mjs`:
 *     node tools/loi-may-chu-harness.mjs /tmp/loi-may-chu.html
 */
import { writeFileSync } from "node:fs";
import React from "react";
// react-native-web directly, never "react-native": this file is not compiled
// through the step that rewrites that specifier, and the real package ships
// Flow syntax node cannot parse.
import { AppRegistry, View } from "react-native-web";

import { TimKhongDuoc } from "../dist-test/screens/kham-pha/CauAiHieu.js";
import { ChuaCoDuLieu } from "../dist-test/screens/kham-pha/KhamPha.js";
import { Screen } from "../dist-test/ui/Kit.js";

const BASE = "http://api.test.invalid";

/* The three bodies measured on a real browser in rd-qa-20, verbatim, plus the
 * long one the excerpt exists for. `places.ts` and `tim-kiem.ts` hand the
 * screen at most 200 characters, so that is the widest input this can get. */
const THAN = [
  { status: 500, detail: "Internal Server Error" },
  { status: 502, detail: "<html>502 Bad Gateway</html>" },
  { status: 429, detail: '{"detail":"rate limited"}' },
  {
    status: 500,
    detail:
      'Traceback (most recent call last): File "/srv/api-internal-7/app/db/repository.py", line 412, in doc cur.execute("SELECT token, phone FROM people WHERE id=%s", (pid,)) psycopg.Op'.slice(
        0,
        200,
      ),
  },
];

/* The three refusals that carry no server body at all (bug-191433). They are on
 * this page for the opposite reason the four above are: those got longer, these
 * are the longest copy on the screen *without* an excerpt to blame, because the
 * whole point of them is that the app explains the situation in its own words
 * instead of forwarding `authentication_required` or the limiter's sentence. A
 * paragraph of Vietnamese with no `Chi tiết:` line under it is a different
 * shape to measure -- line length and card rhythm, not overflow from a blob. */
const KHONG_CO_THAN = [
  { kind: "chua-biet-la-ai" },
  { kind: "bi-tu-choi", url: `${BASE}/places/search` },
  { kind: "qua-nhieu-lan", query: "quán nướng ngoài trời cho 6 người dưới 300k" },
];

function Trang() {
  return React.createElement(
    Screen,
    { title: "Khám phá", hint: "Chỗ hợp với nhóm, do máy chủ chấm." },
    React.createElement(
      View,
      { style: { gap: 16 } },
      // Search card and catalogue card interleaved: the two say a slightly
      // different sentence for the same status, and whether that reads as two
      // deliberate messages or as an inconsistency is a thing to look at side
      // by side rather than one page at a time.
      THAN.flatMap((t, i) => [
        React.createElement(TimKhongDuoc, {
          key: `tim-${i}`,
          state: { kind: "may-chu-loi", url: `${BASE}/places/search`, ...t },
          baseUrl: BASE,
        }),
        React.createElement(ChuaCoDuLieu, {
          key: `muc-${i}`,
          state: { kind: "may-chu-loi", url: `${BASE}/places`, ...t },
        }),
      ]),
      KHONG_CO_THAN.map((state, i) =>
        React.createElement(TimKhongDuoc, { key: `gate-${i}`, state, baseUrl: BASE }),
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
<title>Khám phá khi máy chủ trả lỗi</title>
${renderToStaticMarkup(getStyleElement())}
</head>
<body>${renderToStaticMarkup(element)}</body>
</html>`;

writeFileSync(process.argv[2], html);
console.log(`viết ${process.argv[2]} (${html.length} byte)`);
