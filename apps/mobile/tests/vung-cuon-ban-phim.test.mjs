/* The one keyboard tab-stop on Cá nhân, measured on emitted markup.
 *
 * rd-qa-07 measured this with axe-core 4.13 (wcag2a + wcag2aa + wcag22aa) on a
 * web export at 390x844:
 *
 *     scrollable-region-focusable  serious  WCAG 2.1.1 + 2.1.3
 *     target: .r-150rngu.r-eqz5dr.r-16y2uox > .r-150rngu.r-eqz5dr.r-16y2uox
 *     why:    Element should have focusable content / Element should be focusable
 *
 * Cá nhân is the one tab that holds nothing pressable -- numbers, rows and
 * labels, nothing else. Every other tab has buttons, and a scrollable region
 * containing a focusable child is already reachable, which is why axe fired
 * here and on none of the other four. With no stop on the scroller there is no
 * key that scrolls this screen, so the transaction list and "Nhóm của bạn"
 * below the fold cannot be read by a keyboard at all.
 *
 * ## Why this file exists at all
 *
 * The fix (`tabIndex={0}` on the `ScrollView`) landed in #99 and shipped
 * unguarded. Measured on 2026-08-29 at main @ 8533aa8: deleting that one line
 * left the whole suite green at 328/328. The screen was correct and nothing
 * was holding it correct, which is the state this file ends.
 *
 * It reads markup rather than source on purpose. `focusable` compiles exactly
 * as well as `tabIndex` and is the spelling react-native-web 0.21 deprecates
 * -- it reaches the DOM as nothing, the same way `accessibilityState` does in
 * `aria-state.test.mjs`. A grep for "the prop is present" would pass on a
 * screen no keyboard can scroll. Only the emitted attribute settles it.
 *
 * What this proves: the attribute react-native-web emits for the browser, in
 * the render `expo export` performs. What it does not prove: iOS or Android,
 * where the prop is ignored by design (a touch screen has no tab ring), nor
 * that a real screen reader announces anything -- for that, the rendered axe
 * pass in `tests/qa/rd-qa-07/02-a11y-ca-nhan.mjs`.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaNhan } from "../dist-test/screens/ca-nhan/CaNhan.js";

/** Opening tags in document order, each with its attributes. Cheap on purpose:
 *  the question here is about the outermost two elements, not about parentage
 *  deeper in, so this deliberately does not build a tree the way
 *  `aria-vai-tro.test.mjs` has to. */
function openingTags(html) {
  return [...html.matchAll(/<([a-zA-Z][\w:-]*)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*\/?>/g)].map(
    ([, name, rawAttrs]) => ({
      name,
      attrs: Object.fromEntries(
        [...rawAttrs.matchAll(/([\w:-]+)(?:="([^"]*)")?/g)].map(([, k, v]) => [k, v ?? ""]),
      ),
    }),
  );
}

/** A person, because the screen renders a name before any request resolves.
 *  `useEffect` does not run under `renderToStaticMarkup`, so what this
 *  measures is the first paint -- which is exactly when a keyboard user
 *  arrives, and so exactly when the stop has to already be there. */
const NGUOI = { id: "p-minh", name: "Minh" };

function markup() {
  return renderToStaticMarkup(React.createElement(CaNhan, { nguoi: NGUOI }));
}

test("Cá nhân: vùng cuộn mang đúng một điểm dừng bàn phím", () => {
  const tags = openingTags(markup());
  const stops = tags.filter((t) => t.attrs.tabindex === "0");

  assert.equal(
    stops.length,
    1,
    `Cá nhân phải có đúng một điểm dừng bàn phím trên vùng cuộn, đang có ${stops.length}. ` +
      `Không có điểm dừng nào thì không phím nào cuộn được màn này ` +
      `(axe: scrollable-region-focusable, serious, WCAG 2.1.1) — ` +
      `phần dưới màn không ai đọc tới được bằng bàn phím.`,
  );
});

test("điểm dừng nằm trên chính vùng cuộn, không phải một ô nào bên trong", () => {
  // react-native-web renders a ScrollView as a wrapper div holding the
  // scrolling div; `tabIndex` lands on the inner one, which is the element axe
  // named as the target. Anything deeper would be a stop on a card or a row --
  // it would satisfy "has focusable content" while still leaving the region
  // itself unreachable, and would move focus somewhere that reads nothing.
  const tags = openingTags(markup());
  const viTri = tags.findIndex((t) => t.attrs.tabindex === "0");

  assert.ok(
    viTri === 0 || viTri === 1,
    `điểm dừng đang nằm ở phần tử thứ ${viTri + 1} của màn, không phải trên vùng cuộn ` +
      `(phần tử 1 hoặc 2). Một điểm dừng sâu bên trong làm axe im lặng mà bàn phím vẫn ` +
      `không cuộn được.`,
  );
});
