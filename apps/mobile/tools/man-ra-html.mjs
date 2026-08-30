/** Render one screen to a real HTML page, so a detector can actually read it.
 *
 * ## Why this exists
 *
 * `imp detect` is blind to React Native `.tsx`. Measured on this branch, with
 * the same deliberately-bad content written twice:
 *
 *     Xau.tsx   -> []          exit 0
 *     xau.html  -> 6 findings  exit 2
 *
 * Same colours, same font sizes, same over-long line. So a `[]` on any screen
 * in `src/` is the scanner declining to parse the file, not a clean screen --
 * and it reads exactly like a pass. Every "detector clean" claim made against
 * a `.tsx` path in this repository is worth nothing, including the ones made
 * in good faith.
 *
 * ## Why static markup alone is not enough either
 *
 * `renderToStaticMarkup` emits class names and no stylesheet. A detector fed
 * that computes contrast against nothing and reports a clean page for the same
 * reason -- it cannot see a colour that only exists in CSS it was not given.
 *
 * react-native-web has the documented server path for precisely this:
 * `AppRegistry.getApplication()` returns the element *and* `getStyleElement()`,
 * the `<style>` block holding the atomic CSS those class names resolve
 * through. Both together are the page a browser would actually paint, which is
 * what makes the contrast numbers real.
 *
 * ## What this does NOT prove
 *
 * It is one static state of the screen, at whatever props are passed. It is
 * not a browser: no layout, no fonts loaded, no media queries evaluated
 * against a viewport. So geometry rules (line length in rendered characters,
 * text near the viewport edge) are still measuring an approximation, and only
 * a served page with `imp detect <url>` settles those. What it does settle is
 * every rule that reads colour, size and structure -- which is where this
 * project's real defects have been.
 *
 * Usage:
 *   node tools/man-ra-html.mjs <dist-test/path/Man.js> <TenExport> <ra.html> ['{"prop":1}']
 */
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

import React from "react";
import { AppRegistry } from "react-native-web";

const [, , duongDan, tenExport, raFile, propsJson] = process.argv;

if (!duongDan || !tenExport || !raFile) {
  console.error(
    "dùng: node tools/man-ra-html.mjs <dist-test/.../Man.js> <TenExport> <ra.html> ['{props}']",
  );
  process.exit(2);
}

const mod = await import(resolve(duongDan));
const Man = mod[tenExport];
if (typeof Man !== "function") {
  // Naming a missing export must not produce an empty page that then scans
  // clean -- that would be the same false pass one layer further down.
  console.error(`không có export "${tenExport}" trong ${duongDan}`);
  process.exit(2);
}

const props = propsJson ? JSON.parse(propsJson) : {};

AppRegistry.registerComponent("Man", () => (p) => React.createElement(Man, { ...p, ...props }));
const { element, getStyleElement } = AppRegistry.getApplication("Man", {});

const { renderToStaticMarkup } = await import("react-dom/server");
const than = renderToStaticMarkup(element);
const style = renderToStaticMarkup(getStyleElement());

// `lang="vi"` because the copy is Vietnamese and a document with no language
// is its own accessibility finding; the point of this file is to be measured
// honestly, and shipping a page that fails for a reason the screen is not
// responsible for would poison the number in the other direction.
const html = `<!doctype html>
<html lang="vi">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${tenExport}</title>
${style}
</head>
<body>${than}</body>
</html>
`;

writeFileSync(raFile, html);
// Bare floors, printed rather than asserted: a page that came out suspiciously
// small is the tell that the render failed quietly, and the reader needs to see
// the number before they trust a scan of it.
console.log(`${raFile}: ${html.length} byte, ${than.length} byte thân, ${style.length} byte style`);
