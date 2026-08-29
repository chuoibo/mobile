/* Two roles the accessibility tree throws away, measured on the real markup.
 *
 * Both were found by axe-core 4.13 (wcag2a + wcag2aa + wcag22aa) on a web
 * export of `main`, at 390x844, with the scanner proven alive first by
 * injecting an `<img>` with no alt and a `<button>` with no name and watching
 * it catch both. Numbers from that run:
 *
 *     aria-prohibited-attr   serious   x12   <- the map dots on Khám phá
 *     aria-required-children critical  x1    <- the bottom tab bar
 *
 * ## 1. Twelve names that no screen reader is allowed to read
 *
 * `DaiBanDo` gave each dot `accessibilityLabel={p.name}`, which reaches the
 * browser as a bare `<div aria-label="Tiệm Nướng Xóm Lào">` -- no role, no
 * tabindex. ARIA prohibits a name on an element with no role, so the whole
 * label is *dropped*: this is not "a weak label", it is no label. Read out of
 * Chromium before the fix, every one of the twelve:
 *
 *     {"tag":"DIV","role":null,"label":"Tiệm Nướng Xóm Lào","tabindex":null,"w":14,"h":14}
 *
 * The fix does not turn each dot into a control. The catalogue is two cities
 * 200 km apart -- eight places in Đà Lạt, four in TP.HCM -- so under the
 * strip's linear projection eight of the twelve dots land within 1-2 px of
 * each other:
 *
 *     89.17% / 18.88%  Chill Đêm Đà Lạt
 *     89.22% / 19.05%  Tiệm Nướng Xóm Lào     <- 0.0 px apart, measured
 *     89.42% / 19.20%  An Cafe Đà Lạt
 *
 * Twelve tab stops on marks a pointer can never separately hit would trade one
 * defect for a worse one. The strip is a diagram, so it is named as one: a
 * single `role="img"` carrying every place name, which is the pattern WAI
 * gives for a simple image with a text alternative. The dots below it are
 * decorative and carry nothing.
 *
 * ## 2. A tablist with something in it that is not a tab
 *
 * The bar declared `role="tablist"` over five children, and the middle one --
 * the wrapper around the raised [+] -- had no role and no name:
 *
 *     1 DIV role=tab   "Khám phá — gợi ý chỗ đi cho nh"
 *     3 DIV role=null  ""                                <- [+]
 *
 * [+] is not a tab: it opens a create menu and leaves you on the screen you
 * were on. So it moves out of the tablist rather than being given a tab role
 * it does not deserve.
 *
 * ## What this file proves, and what it does not
 *
 * It renders through `react-native-web`, the same substitution `expo export`
 * performs, so these are the attributes a browser really receives -- the same
 * reason `aria-state.test.mjs` renders instead of reading source. It does not
 * prove anything about iOS or Android, and it is not a substitute for axe:
 * axe reads computed roles and this file reads emitted attributes. It is the
 * cheap net that runs on every `npm test` with no browser, under the browser
 * gate in `vo-tab-web.test.mjs`.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DaiBanDo } from "../dist-test/screens/kham-pha/DaiBanDo.js";
import { ThanhTab } from "../dist-test/navigation/ThanhTab.js";
import { TABS } from "../dist-test/navigation/tabs.js";

/* --------------------------------------------------------------- markup --- */

/** Elements that have no HTML close tag, so the parser must not push them. */
const VOID = new Set([
  "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr",
]);

/**
 * Parse React's static markup into a tree.
 *
 * A tree, not a flat list, because the defect in the tab bar is about *direct*
 * children of the tablist -- `aria-required-children` is a question about
 * parentage, and a regex over the whole document cannot answer it. Text nodes
 * are dropped; nothing here asks about them.
 */
function parse(html) {
  const root = { name: "#root", attrs: {}, children: [] };
  const stack = [root];
  const tag = /<(\/?)([a-zA-Z][\w:-]*)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*(\/?)>/g;

  for (const [, closing, name, rawAttrs, selfClosing] of html.matchAll(tag)) {
    if (closing) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const node = {
      name,
      attrs: Object.fromEntries(
        [...rawAttrs.matchAll(/([\w:-]+)(?:="([^"]*)")?/g)].map(([, k, v]) => [k, v ?? ""]),
      ),
      children: [],
    };
    stack[stack.length - 1].children.push(node);
    if (!selfClosing && !VOID.has(name)) stack.push(node);
  }

  assert.equal(stack.length, 1, "markup không cân bằng thẻ — parser đọc sai");
  return root;
}

function walk(node, out = []) {
  for (const child of node.children) {
    out.push(child);
    walk(child, out);
  }
  return out;
}

function render(component, props) {
  return parse(renderToStaticMarkup(React.createElement(component, props)));
}

/** Elements that carry an accessible name from HTML alone, so `aria-label` on
 *  them is allowed with no explicit `role`. Everything react-native-web emits
 *  for a `View` or a `Text` is a `div`, which is not one of these. */
const NAMEABLE_WITHOUT_ROLE = new Set([
  "a", "button", "input", "select", "textarea", "img", "iframe", "summary", "area",
]);

/** Every element axe would report under `aria-prohibited-attr`. */
function prohibitedNames(tree) {
  return walk(tree)
    .filter((el) => "aria-label" in el.attrs)
    .filter((el) => !el.attrs.role && !NAMEABLE_WITHOUT_ROLE.has(el.name))
    .map((el) => `<${el.name} aria-label="${el.attrs["aria-label"]}">`);
}

/* ------------------------------------------------------------- fixtures --- */

/** Four places from the seed catalogue, coordinates unchanged. Two in Đà Lạt
 *  and two in TP.HCM, so the fixture keeps the two-cluster shape that makes
 *  per-dot targets impossible; a fixture spread evenly over the box would
 *  quietly argue for the wrong fix. */
function place(id, name, lat, lng, source) {
  return {
    id,
    name,
    category: "quan-an-local",
    kinds: ["BBQ"],
    rating: 4.7,
    ratingCount: 128,
    distanceKm: 1.2,
    priceMinVnd: 200000,
    priceMaxVnd: 250000,
    address: "27/1 Yersin, TP. Đà Lạt",
    openNow: true,
    openHours: "16:00 – 23:00",
    travelMinutes: 8,
    photoCount: 3,
    traits: [],
    groupFit: null,
    flag: null,
    lat,
    lng,
    match: source ? { score: 92, reason: "hợp", source, verdict: "hop", factors: [] } : null,
  };
}

const PLACES = [
  place("p-tiem-nuong-xom-lao", "Tiệm Nướng Xóm Lào", 11.9404, 108.4383, "ai"),
  place("p-chill-dem", "Chill Đêm Đà Lạt", 11.9435, 108.4372, null),
  place("p-quan-oc-di-be", "Quán Ốc Dì Bé", 10.7561, 106.7024, "ai"),
  place("p-the-hill", "The Hill Rooftop", 10.7702, 106.6944, null),
];

function tabBar(menuOpen = false) {
  return render(ThanhTab, {
    active: "kham-pha",
    menuOpen,
    onSelect: () => {},
    onCreate: () => {},
  });
}

/* ------------------------------------------- 1. the dots on Khám phá --- */

test("dải bản đồ: không chấm nào mang tên trên phần tử không có role", () => {
  // The exact shape axe calls `aria-prohibited-attr`. Before the fix this
  // listed one entry per place; a name there is a name nobody hears.
  const offenders = prohibitedNames(render(DaiBanDo, { places: PLACES }));
  assert.deepEqual(
    offenders,
    [],
    `còn ${offenders.length} phần tử mang aria-label mà không có role — ` +
      `ARIA cấm, trình đọc màn hình bỏ qua: ${offenders.join(" ")}`,
  );
});

test("dải bản đồ nói ra tên của tất cả các chỗ nó vẽ", () => {
  const tree = render(DaiBanDo, { places: PLACES });
  const graphics = walk(tree).filter((el) => el.attrs.role === "img");

  // One name for the whole diagram, not one per mark: the marks overlap.
  assert.equal(graphics.length, 1, "dải bản đồ phải là đúng một hình có tên");
  const name = graphics[0].attrs["aria-label"] ?? "";

  for (const p of PLACES) {
    assert.ok(name.includes(p.name), `tên "${p.name}" không có trong nhãn: "${name}"`);
  }
  assert.match(name, /4/, "nhãn phải nói có bao nhiêu chỗ");
});

test("dải bản đồ trống thì không dựng hình rỗng để lấy tiếng", () => {
  // A `role="img"` with a name but nothing drawn is a lie told to a screen
  // reader only. The component already returns null; this keeps it that way.
  const noCoords = [{ ...PLACES[0], lat: Number.NaN, lng: Number.NaN }];
  assert.equal(walk(render(DaiBanDo, { places: noCoords })).length, 0);
  assert.equal(walk(render(DaiBanDo, { places: [] })).length, 0);
});

/* --------------------------------------------------- 2. the tab bar --- */

test("con trực tiếp của tablist toàn là tab, không có gì khác lọt vào", () => {
  const lists = walk(tabBar()).filter((el) => el.attrs.role === "tablist");
  assert.equal(lists.length, 1);

  const kids = lists[0].children.map((el) => ({
    role: el.attrs.role ?? null,
    label: el.attrs["aria-label"] ?? "",
  }));

  assert.deepEqual(
    kids.map((k) => k.role),
    ["tab", "tab", "tab", "tab"],
    `tablist có con không phải tab — axe gọi là aria-required-children: ${JSON.stringify(kids)}`,
  );
  assert.deepEqual(kids.map((k) => k.label), TABS.map((t) => t.a11yLabel));
});

test("nút [+] vẫn còn, vẫn là button, và nằm ngoài tablist", () => {
  // Moving it out must not lose it, and must not quietly turn it into a tab:
  // it opens a menu and leaves you where you were.
  for (const open of [false, true]) {
    const tree = tabBar(open);
    const label = open ? "Đóng menu tạo mới" : "Tạo mới";
    const plus = walk(tree).filter((el) => el.attrs["aria-label"] === label);

    assert.equal(plus.length, 1, `không thấy nút [+] với nhãn "${label}"`);
    assert.equal(plus[0].attrs.role, "button");
    assert.equal(plus[0].attrs["aria-expanded"], String(open));

    const list = walk(tree).find((el) => el.attrs.role === "tablist");
    assert.ok(
      !walk(list).includes(plus[0]),
      "nút [+] vẫn nằm trong tablist — đó chính là lỗi cần sửa",
    );
  }
});

test("bốn tab vẫn khai đúng một tab đang chọn", () => {
  // The bar was restructured; this is the check that the restructure did not
  // undo what #78 fixed.
  const tabs = walk(tabBar()).filter((el) => el.attrs.role === "tab");
  assert.equal(tabs.length, 4);
  assert.deepEqual(
    tabs.map((t) => t.attrs["aria-selected"]),
    ["true", "false", "false", "false"],
  );
});

/* ------------------------------------------------------------ the net --- */

test("không màn nào của lane này mang aria-label trên phần tử không role", () => {
  // Generic, so the next `<View accessibilityLabel=…>` somebody adds to these
  // two components is caught without anyone remembering this file exists.
  for (const [name, tree] of [
    ["ThanhTab", tabBar()],
    ["ThanhTab (menu mở)", tabBar(true)],
    ["DaiBanDo", render(DaiBanDo, { places: PLACES })],
  ]) {
    const offenders = prohibitedNames(tree);
    assert.deepEqual(offenders, [], `${name}: ${offenders.join(" ")}`);
  }
});
